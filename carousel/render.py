#!/usr/bin/env python3
"""Render the 10800×1920 carousel via Chrome CDP, then slice into 10 stories."""
from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPORT = ROOT / "export"
MASTER_PNG = EXPORT / "master.png"
MASTER_JPG = EXPORT / "master.jpg"
SLIDES = EXPORT / "slides"
HTML = ROOT / "index.html"
W, H, COL = 10800, 1920, 1080


def wait_port(port: int, timeout: float = 25.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.4):
                return
        except OSError:
            time.sleep(0.12)
    raise RuntimeError(f"Chrome debug port {port} did not open")


class CDP:
    def __init__(self, ws_url: str):
        try:
            import websocket  # type: ignore
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "websocket-client"])
            import websocket  # type: ignore
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self.n = 0

    def send(self, method: str, params: dict | None = None, timeout: float = 45.0):
        self.n += 1
        nid = self.n
        payload: dict = {"id": nid, "method": method}
        if params:
            payload["params"] = params
        self.ws.send(json.dumps(payload))
        t0 = time.time()
        while time.time() - t0 < timeout:
            data = json.loads(self.ws.recv())
            if data.get("id") == nid:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})
        raise TimeoutError(method)

    def wait_event(self, name: str, timeout: float = 20.0) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            data = json.loads(self.ws.recv())
            if data.get("method") == name:
                return
        raise TimeoutError(name)

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def chrome_screenshot() -> None:
    EXPORT.mkdir(parents=True, exist_ok=True)
    port = 9222
    user_data = tempfile.mkdtemp(prefix="chrome-carousel-")
    proc = subprocess.Popen(
        [
            "google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--font-render-hinting=medium",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}",
            "--remote-allow-origins=*",
            f"--window-size={W},{H}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        wait_port(port)
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
        page = next(p for p in pages if p.get("type") == "page")
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False},
        )
        cdp.send("Page.navigate", {"url": HTML.as_uri()})
        try:
            cdp.wait_event("Page.loadEventFired", timeout=18)
        except TimeoutError:
            time.sleep(2)
        cdp.send(
            "Runtime.evaluate",
            {"expression": "document.fonts.ready.then(()=>document.images.length)", "awaitPromise": True},
            timeout=20,
        )
        # wait images decode
        cdp.send(
            "Runtime.evaluate",
            {
                "expression": (
                    "Promise.all([...document.images].map(img => "
                    "img.complete ? Promise.resolve() : new Promise(r => { img.onload=r; img.onerror=r; })))"
                ),
                "awaitPromise": True,
            },
            timeout=20,
        )
        time.sleep(0.5)
        result = cdp.send(
            "Page.captureScreenshot",
            {
                "format": "png",
                "fromSurface": True,
                "captureBeyondViewport": True,
                "clip": {"x": 0, "y": 0, "width": W, "height": H, "scale": 1},
            },
            timeout=90,
        )
        cdp.close()
        MASTER_PNG.write_bytes(base64.b64decode(result["data"]))
        print("captured", MASTER_PNG, MASTER_PNG.stat().st_size)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()


def slice_export() -> None:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(MASTER_PNG).convert("RGB")
    print("bitmap", im.size)
    if im.size != (W, H):
        print(f"WARNING: captured {im.size}, expected {(W, H)}", file=sys.stderr)
        im = im.resize((W, H), Image.Resampling.LANCZOS)
    im.save(MASTER_JPG, "JPEG", quality=93, subsampling=1, optimize=True)
    SLIDES.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        crop = im.crop((i * COL, 0, (i + 1) * COL, H))
        out = SLIDES / f"{i + 1:02d}.jpg"
        crop.save(out, "JPEG", quality=93, subsampling=1, optimize=True)
        print("wrote", out.name, crop.size)
    sheet = im.resize((W // 4, H // 4), Image.Resampling.LANCZOS)
    sheet.save(EXPORT / "contact_sheet.jpg", "JPEG", quality=90)
    print("master_jpg", MASTER_JPG.stat().st_size)


if __name__ == "__main__":
    os.chdir(ROOT)
    chrome_screenshot()
    slice_export()
