"""
ScreenAnalyzer
==============
Detects game items using OpenCV template matching.
All coordinates are relative to the game window (not the full screen).
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class DetectedItem:
    label:      str
    cx:         int     # center X  (window-relative)
    cy:         int     # center Y  (window-relative)
    confidence: float
    grid_row:   int = -1
    grid_col:   int = -1


class ScreenAnalyzer:
    """
    Template-matching item detector.

    Grid calibration
    ----------------
    The game's play area is roughly rectangular.
    Measure the pixel position of the top-left cell center and
    the spacing between cells in your emulator window, then set:

        GRID_ORIGIN_X / Y  — pixel of cell (row=0, col=0)
        CELL_W / CELL_H    — pixels between adjacent cells

    Run  python bot.py --debug-once  to see an annotated overlay
    and fine-tune until all items snap to the correct grid squares.
    """

    # ── Tune these to your emulator window size ────────────────────────
    GRID_ORIGIN_X = 100
    GRID_ORIGIN_Y = 220
    CELL_W        = 95
    CELL_H        = 80
    GRID_COLS     = 9
    GRID_ROWS     = 8
    # ───────────────────────────────────────────────────────────────────

    def __init__(self, templates_dir: str = "templates",
                 match_threshold: float = 0.72):
        self.templates_dir = templates_dir
        self.threshold     = match_threshold
        self.templates: dict[str, np.ndarray] = {}
        self._load_templates()

    # ──────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────

    def analyze(self, frame: np.ndarray) -> list[DetectedItem]:
        """Detect all known items. frame = RGB numpy array."""
        gray     = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        detected = []

        for label, tmpl_data in self.templates.items():
            detected.extend(self._match(gray, tmpl_data, label))

        for item in detected:
            item.grid_row, item.grid_col = self.pixel_to_grid(item.cx, item.cy)

        return sorted(detected, key=lambda d: (d.grid_row, d.grid_col))

    def build_grid(self, items: list[DetectedItem]) -> dict[int, DetectedItem]:
        # bypasses the strict (row, col) grid so items never overwrite each other
        return {idx: item for idx, item in enumerate(items)}

    def find_merge_groups(
        self, grid: dict[int, DetectedItem]
    ) -> list[list[DetectedItem]]:
        """Return lists of 3+ items with the same label."""
        by_label: dict[str, list] = defaultdict(list)
        for item in grid.values():
            by_label[item.label].append(item)
        return [items for items in by_label.values() if len(items) >= 3]

    def find_merge_groups(
        self, grid: dict[tuple, DetectedItem]
    ) -> list[list[DetectedItem]]:
        """Return lists of 2+ cells with the same label."""
        by_label: dict[str, list] = defaultdict(list)
        for item in grid.values():
            by_label[item.label].append(item)
        return [items for items in by_label.values() if len(items) >= 2]

    def pixel_to_grid(self, px: int, py: int) -> tuple[int, int]:
        col = round((px - self.GRID_ORIGIN_X) / self.CELL_W)
        row = round((py - self.GRID_ORIGIN_Y) / self.CELL_H)
        col = max(0, min(col, self.GRID_COLS - 1))
        row = max(0, min(row, self.GRID_ROWS - 1))
        return row, col

    def grid_to_pixel(self, row: int, col: int) -> tuple[int, int]:
        px = self.GRID_ORIGIN_X + col * self.CELL_W
        py = self.GRID_ORIGIN_Y + row * self.CELL_H
        return px, py

    def debug_annotate(
        self, frame: np.ndarray, items: list[DetectedItem]
    ) -> np.ndarray:
        out = frame.copy()
        # Draw grid lines
        for r in range(self.GRID_ROWS + 1):
            y = self.GRID_ORIGIN_Y + r * self.CELL_H
            cv2.line(out, (self.GRID_ORIGIN_X, y),
                     (self.GRID_ORIGIN_X + self.GRID_COLS * self.CELL_W, y),
                     (60, 60, 60), 1)
        for c in range(self.GRID_COLS + 1):
            x = self.GRID_ORIGIN_X + c * self.CELL_W
            cv2.line(out, (x, self.GRID_ORIGIN_Y),
                     (x, self.GRID_ORIGIN_Y + self.GRID_ROWS * self.CELL_H),
                     (60, 60, 60), 1)
        # Draw detected items
        for item in items:
            cv2.circle(out, (item.cx, item.cy), 22, (0, 255, 80), 2)
            cv2.putText(out, f"{item.label[:10]}",
                        (item.cx - 30, item.cy - 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 240, 0), 1)
            cv2.putText(out, f"({item.grid_row},{item.grid_col})",
                        (item.cx - 20, item.cy + 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 220, 255), 1)
        return out

    # ──────────────────────────────────────────────
    # INTERNAL
    # ──────────────────────────────────────────────

    def _load_templates(self):
        if not os.path.isdir(self.templates_dir):
            print(f"[Analyzer] ⚠  '{self.templates_dir}' not found.")
            return
        count = 0
        for fname in sorted(os.listdir(self.templates_dir)):
            if fname.endswith(".png"):
                label = fname[:-4]
                path = os.path.join(self.templates_dir, fname)
                
                # Load the image WITH the alpha transparency channel
                img_bgra = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img_bgra is None:
                    continue
                    
                # If the image has transparency (4 channels: Blue, Green, Red, Alpha)
                if len(img_bgra.shape) == 3 and img_bgra.shape[2] == 4:
                    alpha = img_bgra[:, :, 3] # The transparency mask
                    bgr = img_bgra[:, :, :3]
                    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                    
                    self.templates[label] = {"img": gray, "mask": alpha}
                else:
                    # Normal image without transparency
                    gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    self.templates[label] = {"img": gray, "mask": None}
                count += 1
        print(f"[Analyzer] Loaded {count} templates with transparency support!")

    def _match(self, gray: np.ndarray, tmpl_data: dict, label: str) -> list[DetectedItem]:
        tmpl = tmpl_data["img"]
        mask = tmpl_data["mask"]
        th, tw = tmpl.shape[:2]

        if gray.shape[0] < th or gray.shape[1] < tw:
            return []

        if mask is not None:
            tmpl = cv2.bitwise_and(tmpl, tmpl, mask=mask)
            # FIX 1: Use CCOEFF_NORMED which matches on shape/contrast, ignoring bright grass
            result = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED, mask=mask)
            # Because this is stricter, 0.80 is the perfect sweet spot again
            ys, xs = np.where(result >= 0.80) 
        else:
            result = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= self.threshold)

        raw = []
        for x, y in zip(xs, ys):
            conf = float(result[y, x])
            cx   = x + tw // 2
            cy   = y + th // 2
            raw.append((cx, cy, conf))

        # FIX 2: Delete duplicates FIRST. 
        # Increased min_dist to 60px so it only allows ONE match per grid square.
        unique_items = self._nms(raw, min_dist=60) 

        # FIX 3: THEN apply the Top 10 filter to prevent phantom matches
        if len(unique_items) > 10:
            unique_items = sorted(unique_items, key=lambda i: i[2], reverse=True)[:10]

        return [DetectedItem(label=label, cx=cx, cy=cy, confidence=conf)
                for cx, cy, conf in unique_items]
    
    def _nms(self, matches: list[tuple[int, int, float]], min_dist: int = 60) -> list[tuple[int, int, float]]:
        """
        Non-Maximum Suppression.
        Removes duplicate matches that are too close to each other.
        """
        # Sort by confidence (highest first)
        matches = sorted(matches, key=lambda m: m[2], reverse=True)
        
        kept = []
        for match in matches:
            cx, cy, conf = match
            is_valid = True
            
            # Check distance against all already-kept matches
            for kx, ky, kconf in kept:
                dist = ((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5
                if dist < min_dist:
                    is_valid = False
                    break
                    
            if is_valid:
                kept.append(match)
                
        return kept