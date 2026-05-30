"""
select_region.py
================
Run this ONCE to define the exact game area inside Discord.
"""
import sys
import ctypes

# Force Windows to map physical pixels 1:1 with logical pixels
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # Windows 10/11
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware() # Fallback
        except Exception:
            pass
import os
import json
import time
import cv2
import numpy as np
import mss
from PIL import Image

CONFIG_DIR  = "config"
REGION_FILE = os.path.join(CONFIG_DIR, "region.json")
os.makedirs(CONFIG_DIR, exist_ok=True)

class RegionSelector:
    def __init__(self):
        self.dragging  = False
        self.start_pt  = None
        self.end_pt    = None
        self.confirmed = False

        print("[Setup] Taking full-screen screenshot...")
        with mss.mss() as sct:
            mon   = sct.monitors[1]   # primary monitor
            raw   = sct.grab(mon)
            img   = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            self.full_frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            self.screen_w   = mon["width"]
            self.screen_h   = mon["height"]

        self.display = self.full_frame.copy()
        self.scale   = min(1.0, 1400 / self.screen_w, 900 / self.screen_h)

    def run(self) -> dict | None:
        print("\n════════════════════════════════════════════════")
        print("  Farm Merge Bot — Game Region Setup")
        print("════════════════════════════════════════════════")
        print("  DRAG  → draw a box around the game area")
        print("  ENTER → confirm selection")
        print("  R     → reset and redraw")
        print("  Q     → quit without saving")
        print("════════════════════════════════════════════════")

        win_name = "Select Game Region — drag over the game, then press ENTER"
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

        dw = int(self.screen_w * self.scale)
        dh = int(self.screen_h * self.scale)
        cv2.resizeWindow(win_name, dw, dh)
        cv2.setMouseCallback(win_name, self._on_mouse)

        while True:
            cv2.imshow(win_name, self.display)
            key = cv2.waitKey(20) & 0xFF

            if key == 13 or key == ord("\r"):   # Enter
                if self.start_pt and self.end_pt:
                    break
                else:
                    print("  Draw a rectangle first.")

            elif key == ord("r"):
                self.start_pt = self.end_pt = None
                self.display  = self.full_frame.copy()
                print("  Reset — draw again.")

            elif key == ord("q"):
                cv2.destroyAllWindows()
                print("  Cancelled.")
                return None

        cv2.destroyAllWindows()

        # Coordinates are mapped correctly intrinsically, do NOT divide by scale
        x1 = min(self.start_pt[0], self.end_pt[0])
        y1 = min(self.start_pt[1], self.end_pt[1])
        x2 = max(self.start_pt[0], self.end_pt[0])
        y2 = max(self.start_pt[1], self.end_pt[1])

        region = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

        with open(REGION_FILE, "w") as f:
            json.dump(region, f, indent=2)

        print(f"\n  ✓ Region saved to {REGION_FILE}")
        print(f"    left={x1}  top={y1}  width={x2-x1}  height={y2-y1}")

        preview = self.full_frame[y1:y2, x1:x2]
        cv2.namedWindow("Preview — press any key", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Preview — press any key", min(x2-x1, 800), min(y2-y1, 600))
        cv2.imshow("Preview — press any key", preview)
        print("\n  Preview shown — press any key to close.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        return region

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.dragging = True
            self.start_pt = (x, y)
            self.end_pt   = None

        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            self.display = self.full_frame.copy()
            cv2.rectangle(self.display, self.start_pt, (x, y), (0, 200, 255), 2)
            # Remove the scale calculation, 'x' and 'y' are real pixels
            w = abs(x - self.start_pt[0])
            h = abs(y - self.start_pt[1])
            cv2.putText(self.display, f"{w}x{h}px",
                        (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 200, 255), 2)

        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging = False
            self.end_pt   = (x, y)
            self.display  = self.full_frame.copy()
            cv2.rectangle(self.display, self.start_pt, self.end_pt, (0, 255, 80), 3)
            cv2.putText(self.display, "Press ENTER to confirm  |  R to redraw",
                        (self.start_pt[0], self.start_pt[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 80), 2)

def load_region() -> dict | None:
    if os.path.exists(REGION_FILE):
        with open(REGION_FILE) as f:
            return json.load(f)
    return None

if __name__ == "__main__":
    print("\n[Setup] Switch to Discord! Taking full-screen screenshot in 10 seconds...")
    time.sleep(10)
    selector = RegionSelector()
    region   = selector.run()
    if region:
        print("\nDone! Now run:  python bot.py")