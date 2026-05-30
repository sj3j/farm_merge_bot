"""
BoxClicker
==========
Detects ready boxes/chests (those with a red '!' bubble) and clicks them.
Works purely on the captured window frame — no ADB required.
"""

import cv2
import numpy as np
from core.window_controller import WindowController
from core.screen_analyzer   import ScreenAnalyzer, DetectedItem


# Red '!' bubble color range (HSV)
RED_LOW_1  = np.array([0,   150, 150])
RED_HIGH_1 = np.array([10,  255, 255])
RED_LOW_2  = np.array([170, 150, 150])
RED_HIGH_2 = np.array([180, 255, 255])


class BoxClicker:
    def __init__(self, ctrl: WindowController, analyzer: ScreenAnalyzer):
        self.ctrl     = ctrl
        self.analyzer = analyzer

    def click_all_ready_boxes(self, frame: np.ndarray) -> int:
        """Tap every box that has a red '!' notification. Returns count."""
        centers = self._find_exclamation_centers(frame)
        for cx, cy in centers:
            print(f"  [Box] Clicking box at ({cx}, {cy})")
            self.ctrl.tap(cx, cy)
        return len(centers)

    def find_ready_boxes(self, frame: np.ndarray) -> list[tuple[int, int]]:
        return self._find_exclamation_centers(frame)

    # ──────────────────────────────────────────────
    # Red '!' detection
    # ──────────────────────────────────────────────

    def _find_exclamation_centers(self, frame: np.ndarray) -> list[tuple[int,int]]:
        hsv   = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        mask  = cv2.bitwise_or(
            cv2.inRange(hsv, RED_LOW_1, RED_HIGH_1),
            cv2.inRange(hsv, RED_LOW_2, RED_HIGH_2),
        )
        kern  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask  = cv2.morphologyEx(mask, cv2.MORPH_OPEN,   kern)
        mask  = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kern)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        centers = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 80 < area < 2500:
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"]) + 55  # tap the box below the bubble
                    centers.append((cx, cy))

        return self._dedup(centers)

    def _dedup(self, pts: list, dist: int = 50) -> list:
        kept = []
        for p in pts:
            if not any(abs(p[0]-k[0]) < dist and abs(p[1]-k[1]) < dist
                       for k in kept):
                kept.append(p)
        return kept
