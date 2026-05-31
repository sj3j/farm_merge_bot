# core/merge_strategy.py

import math
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
from core.screen_analyzer import DetectedItem

MERGE_CHAINS: dict[str, list[str]] = {
    "carrot":    ["carrot", "carrot2", "carrot3"],
    "chick":     ["chick", "chick2", "chick3"],
    "cow":       ["cow", "cow2", "cow3"],
    "goat":      ["goat", "goat2", "goat3"],
    "soybean":   ["soybean", "soybean2"],
    "sugarcane": ["sugarcane", "sugarcane2", "sugarcane3"],
    "weaht":     ["weaht", "weaht2", "weaht3"],
}

LABEL_TIER: dict[str, int] = {
    label: idx
    for chain in MERGE_CHAINS.values()
    for idx, label in enumerate(chain)
}

@dataclass
class MergeAction:
    src:   DetectedItem
    dst:   DetectedItem
    label: str
    tier:  int

    def __str__(self):
        return (f"MERGE  {self.label} (tier {self.tier})  "
                f"px({self.src.cx},{self.src.cy}) → "
                f"px({self.dst.cx},{self.dst.cy})")

class MergeStrategy:

    def __init__(self):
        self.history = defaultdict(int)

    def clear_history(self):
        self.history.clear()

    def plan(self, grid: dict[int, DetectedItem]) -> list[MergeAction]:
        # 0. Deduplicate overlapping items
        unique_items = []
        for item in grid.values():
            if not any(self._dist(item, u) < 30 for u in unique_items):
                unique_items.append(item)

        # 1. Group items by label
        by_label: dict[str, list[DetectedItem]] = defaultdict(list)
        for item in unique_items:
            by_label[item.label].append(item)

        # 2. Priority Sorting Engine: 
        #    Sorts primarily by lowest fail attempts (fresh items first) 
        #    and secondarily by highest tier.
        def get_group_priority(L):
            tier = LABEL_TIER.get(L, 0)
            max_attempts = 0
            for item in by_label[L]:
                loc_key = (L, round(item.cx / 40) * 40, round(item.cy / 40) * 40)
                max_attempts = max(max_attempts, self.history[loc_key])
            return (max_attempts, -tier)

        labels_by_priority = sorted(by_label.keys(), key=get_group_priority)
        all_items_list = list(unique_items)

        # 3. Process exactly ONE group at a time 
        # (bot.py will loop and call this multiple times to clear the board)
        for label in labels_by_priority:
            items = by_label[label]
            if len(items) < 3:
                continue
                
            tier      = LABEL_TIER.get(label, 0)
            remaining = list(items)
            
            while len(remaining) >= 3:
                src1, target = self._closest_pair(remaining)
                remaining.remove(src1)
                remaining.remove(target)
                
                src2 = min(remaining, key=lambda x: self._dist(target, x))
                remaining.remove(src2)
                
                # Memory key based on target location
                loc_key = (label, round(target.cx / 40) * 40, round(target.cy / 40) * 40)
                attempts = self.history[loc_key]

                # Record that we are making an attempt
                self.history[loc_key] += 1

                # --- ATTEMPT 0: Direct Drag (A -> B, C -> B) ---
                if attempts == 0:
                    return [
                        MergeAction(src1, target, label, tier),
                        MergeAction(src2, target, label, tier)
                    ]
                    
                # --- ATTEMPT 1+: Stuck Loop Detected! Swap and merge elsewhere PERMANENTLY ---
                else: 
                    diff_item = self._get_closest_different_item(target, label, all_items_list)
                    if diff_item:
                        # 1. Swap src1 (A) with diff_item (X)
                        # 2. Move src2 (C) to the new location (X)
                        # 3. Move target (B) to the new location (X) to complete the 3-merge
                        return [
                            MergeAction(src1, diff_item, label, tier),
                            MergeAction(src2, diff_item, label, tier),
                            MergeAction(target, diff_item, label, tier)
                        ]
                    else:
                        # Fallback if no different items exist on the board (Empty board scenario)
                        spot1 = self._get_empty_pixel_neighbor(target, all_items_list)
                        if spot1:
                            return [
                                MergeAction(src1, spot1, label, tier),
                                MergeAction(src2, target, label, tier) 
                            ]
                        else:
                            return [
                                MergeAction(src1, target, label, tier),
                                MergeAction(src2, target, label, tier)
                            ]

        # If all items are processed, return empty (this breaks the loop and triggers collection)
        return []

    def best_action(self, grid) -> Optional[MergeAction]:
        acts = self.plan(grid)
        return acts[0] if acts else None

    def _dist(self, a: DetectedItem, b: DetectedItem) -> float:
        return math.sqrt((a.cx - b.cx)**2 + (a.cy - b.cy)**2)

    def _closest_pair(self, items):
        best_d, best = float("inf"), (items[0], items[1])
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                d = self._dist(items[i], items[j])
                if d < best_d:
                    best_d, best = d, (items[i], items[j])
        return best
        
    def _get_closest_different_item(self, target: DetectedItem, current_label: str, all_items: list[DetectedItem]) -> Optional[DetectedItem]:
        """Finds the closest item on the board that is NOT of the current merging type."""
        diff_items = [item for item in all_items if item.label != current_label]
        if not diff_items:
            return None
        return min(diff_items, key=lambda x: self._dist(target, x))
        
    def _get_empty_pixel_neighbor(self, target: DetectedItem, all_items: list[DetectedItem]) -> Optional[DetectedItem]:
        offsets = [(95, 0), (-95, 0), (0, 80), (0, -80), (47, 40), (-47, -40), (47, -40), (-47, 40)]
        for dx, dy in offsets:
            nx, ny = target.cx + dx, target.cy + dy
            is_empty = True
            for item in all_items:
                dist = math.sqrt((item.cx - nx)**2 + (item.cy - ny)**2)
                if dist < 45:
                    is_empty = False
                    break
            if is_empty:
                return DetectedItem(label="empty_slot", cx=int(nx), cy=int(ny), grid_row=0, grid_col=0, confidence=1.0)
        return None