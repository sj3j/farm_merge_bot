"""
capture_templates.py
====================
Interactive tool to crop item sprites directly from your emulator window.
"""
import os
import sys
import time
import cv2
import numpy as np
from PIL import Image

TEMPLATES_DIR = "templates"
os.makedirs(TEMPLATES_DIR, exist_ok=True)

try:
    from core.window_controller import WindowController
    HAVE_WINDOW_CTRL = True
except ImportError:
    HAVE_WINDOW_CTRL = False

FALLBACK_SCREENSHOT = "screenshots/sample.png"

class TemplateCapturer:
    def __init__(self):
        self.frame       = self._grab_frame()       # BGR for OpenCV display
        self.display     = self.frame.copy()
        self.pt1         = None   # first click
        self.pt2         = None   # second click
        self.saved_count = 0

    def run(self):
        print("\n════════════════════════════════════════")
        print("  Farm Merge — Template Capturer")
        print("════════════════════════════════════════")
        print("  LEFT CLICK  → set top-left of crop")
        print("  RIGHT CLICK → set bottom-right + save")
        print("  R           → reset selection")
        print("  S           → refresh screenshot")
        print("  Q           → quit")
        print("════════════════════════════════════════\n")

        cv2.namedWindow("Capturer", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Capturer", 900, 650)
        cv2.setMouseCallback("Capturer", self._on_mouse)
        cv2.imshow("Capturer", self.frame)

        while True:
            cv2.imshow("Capturer", self.display)
            key = cv2.waitKey(20) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                self.pt1 = self.pt2 = None
                self.display = self.frame.copy()
            elif key == ord("s"):
                self.frame   = self._grab_frame()
                self.display = self.frame.copy()
                self.pt1 = self.pt2 = None
                print("[Capturer] Screenshot refreshed.")

        cv2.destroyAllWindows()
        print(f"\n[Capturer] Done — {self.saved_count} templates saved to '{TEMPLATES_DIR}/'")

    def _on_mouse(self, event, x, y, flags, param):
        # OpenCV inherently passes back intrinsic image coordinates.
        # No window math scaling is necessary.
        ix, iy = x, y

        if event == cv2.EVENT_LBUTTONDOWN:
            self.pt1 = (ix, iy)
            self.pt2 = None
            self.display = self.frame.copy()
            cv2.circle(self.display, (ix, iy), 5, (0, 255, 0), -1)
            print(f"  Top-left set: ({ix}, {iy})  — now RIGHT CLICK for bottom-right")

        elif event == cv2.EVENT_RBUTTONDOWN:
            if self.pt1 is None:
                print("  Set top-left first (LEFT click)")
                return
            self.pt2 = (ix, iy)
            x1, y1 = self.pt1
            x2, y2 = self.pt2
            if x2 <= x1 or y2 <= y1:
                print("  ⚠  Bottom-right must be below and to the right of top-left")
                return

            self.display = self.frame.copy()
            cv2.rectangle(self.display, self.pt1, self.pt2, (0, 200, 255), 2)
            cv2.imshow("Capturer", self.display)
            cv2.waitKey(1)

            crop = self.frame[y1:y2, x1:x2]
            label = input(f"  Label for this item [{x1},{y1}→{x2},{y2}]: ").strip()
            if label:
                path = os.path.join(TEMPLATES_DIR, f"{label}.png")
                cv2.imwrite(path, crop)
                self.saved_count += 1
                print(f"  ✓ Saved → {path}  ({x2-x1}×{y2-y1} px)")
            else:
                print("  (skipped)")
            self.pt1 = self.pt2 = None
            self.display = self.frame.copy()

        elif event == cv2.EVENT_MOUSEMOVE and self.pt1:
            self.display = self.frame.copy()
            cv2.rectangle(self.display, self.pt1, (ix, iy), (0, 200, 255), 1)

    def _grab_frame(self) -> np.ndarray:
        if HAVE_WINDOW_CTRL:
            try:
                ctrl  = WindowController()
                frame = ctrl.screenshot()
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"[Capturer] Live capture failed ({e}), using saved screenshot.")

        if os.path.exists(FALLBACK_SCREENSHOT):
            img = cv2.imread(FALLBACK_SCREENSHOT)
            if img is not None:
                return img

        print("[Capturer] ⚠  No screenshot available.")
        print(f"  Run  python select_region.py  first, or save a screenshot to:")
        print(f"  {FALLBACK_SCREENSHOT}")
        sys.exit(1)

if __name__ == "__main__":
    print("\n[Setup] Switch to Discord! Grabbing screenshot in 10 seconds...")
    time.sleep(10)
    TemplateCapturer().run()