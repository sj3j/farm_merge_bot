"""
WindowController (Discord Edition)
====================================
Captures a fixed screen region (the game inside Discord) and sends
mouse events to absolute screen coordinates within that region.

The region is defined by  select_region.py  and saved to config/region.json.
If no region is saved, it falls back to the full primary monitor.

Dependencies:
    pip install mss pyautogui opencv-python Pillow numpy
"""

import os
import json
import time
import numpy as np
import pyautogui
import mss
from PIL import Image

pyautogui.PAUSE    = 0.04
pyautogui.FAILSAFE = True   # move mouse to top-left corner to abort

REGION_FILE = os.path.join("config", "region.json")


class WindowController:
    """
    Captures a specific screen region and sends mouse clicks/drags
    with coordinates relative to that region's top-left corner.
    """

    def __init__(self, region: dict = None):
        """
        region: {"left": x, "top": y, "width": w, "height": h}
                All values are absolute screen pixels.
                If None, loads from config/region.json.
                If that doesn't exist, uses full primary monitor.
        """
        if region:
            self._region = region
        else:
            self._region = self._load_or_fullscreen()

        print(f"[WindowController] Region: "
              f"left={self._region['left']}  top={self._region['top']}  "
              f"{self._region['width']}×{self._region['height']}px")

    # ──────────────────────────────────────────────
    # SCREENSHOT
    # ──────────────────────────────────────────────

    def screenshot(self) -> np.ndarray:
        """
        Capture the game region and return as RGB numpy array.
        Fast — uses MSS, no disk I/O.
        """
        with mss.mss() as sct:
            raw = sct.grab(self._region)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return np.array(img)

    def save_screenshot(self, path: str) -> np.ndarray:
        frame = self.screenshot()
        Image.fromarray(frame).save(path)
        return frame

    # ──────────────────────────────────────────────
    # MOUSE  (coords relative to region top-left)
    # ──────────────────────────────────────────────

    def _abs(self, rel_x: int, rel_y: int) -> tuple[int, int]:
        """Convert region-relative coords to absolute screen coords."""
        return (self._region["left"] + rel_x,
                self._region["top"]  + rel_y)

    def tap(self, x: int, y: int, delay: float = 0.25):
        ax, ay = self._abs(x, y)
        pyautogui.click(ax, ay)
        time.sleep(delay)

    def drag_item(self, x1: int, y1: int, x2: int, y2: int,
                  duration: float = 0.35, delay: float = 0.5):
        """
        Forces a drag state by performing a 'micro-move' after clicking down.
        This bypasses HTML5 canvas anti-bot/synthetic click dropping.
        """
        ax1, ay1 = self._abs(x1, y1)
        ax2, ay2 = self._abs(x2, y2)

        # 1. Move to the center of the item and settle
        pyautogui.moveTo(ax1, ay1, duration=0.2)
        time.sleep(0.2)
        
        # 2. Press down
        pyautogui.mouseDown(button="left")
        time.sleep(0.2)
        
        # 3. THE FIX: The Micro-Drag
        # Move slightly to break the static threshold and trigger the game's drag state
        pyautogui.moveTo(ax1 + 5, ay1 + 5, duration=0.2)
        time.sleep(0.3) # Wait for the item to visually "pop up" in the game
        
        # 4. Drag to the destination
        pyautogui.moveTo(ax2, ay2, duration=duration, tween=pyautogui.linear)
        time.sleep(0.3) # Pause at destination before dropping
        
        # 5. Release and rest
        pyautogui.mouseUp(button="left")
        time.sleep(delay)

    def right_click(self, x: int, y: int, delay: float = 0.2):
        ax, ay = self._abs(x, y)
        pyautogui.rightClick(ax, ay)
        time.sleep(delay)

    def focus(self):
        """Click the center of the region to focus Discord/game."""
        cx = self._region["left"] + self._region["width"]  // 2
        cy = self._region["top"]  + self._region["height"] // 2
        pyautogui.click(cx, cy)
        time.sleep(0.4)

    # ──────────────────────────────────────────────
    # PROPERTIES
    # ──────────────────────────────────────────────

    @property
    def width(self) -> int:
        return self._region["width"]

    @property
    def height(self) -> int:
        return self._region["height"]

    @property
    def region(self) -> dict:
        return self._region

    # ──────────────────────────────────────────────
    # INTERNAL
    # ──────────────────────────────────────────────

    def _load_or_fullscreen(self) -> dict:
        if os.path.exists(REGION_FILE):
            with open(REGION_FILE) as f:
                r = json.load(f)
            print(f"[WindowController] Loaded region from {REGION_FILE}")
            return r

        print("[WindowController] ⚠  No region file found — using full screen.")
        print("  Run  python select_region.py  to define the game area.")
        w, h = pyautogui.size()
        return {"left": 0, "top": 0, "width": w, "height": h}