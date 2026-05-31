# core/merge_strategy.py

import math
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
from core.screen_analyzer import DetectedItem

MERGE_CHAINS: dict[str, list[str]] = {
    "weaht":     ["weaht", "weaht2", "weaht3"],
    "carrot":    ["carrot", "carrot2", "carrot3"],
    "sugarcane": ["sugarcane", "sugarcane2", "sugarcane3"],
    "soybean":   ["soybean", "soybean2", "soybean3"],
    "chick":     ["chick", "chick2", "chick3"],
    "cow":       ["cow", "cow2", "cow3"],
    "goat":      ["goat", "goat2", "goat3"],
    "wrench":    ["wrench", "wrench2", "wrench3", "wrench4"],
    "box":       ["box", "box2"],
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
        """Resets the history when the board is clear or generator is clicked."""
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

        # 2. Priority Sorting Engine 
        def get_group_priority(L):
            tier = LABEL_TIER.get(L, 0)
            max_attempts = 0
            for item in by_label[L]:
                loc_key = (L, round(item.cx / 40) * 40, round(item.cy / 40) * 40)
                max_attempts = max(max_attempts, self.history[loc_key])
            return (max_attempts, -tier)

        labels_by_priority = sorted(by_label.keys(), key=get_group_priority)
        all_items_list = list(unique_items)

        # 3. Process exactly ONE group at a time to prevent game animation desync
        for label in labels_by_priority:
            items = by_label[label]
            if len(items) < 3:
                continue
                
            tier = LABEL_TIER.get(label, 0)
            remaining = list(items)
            
            while len(remaining) >= 3:
                src1, target = self._closest_pair(remaining)
                remaining.remove(src1)
                remaining.remove(target)
                
                src2 = min(remaining, key=lambda x: self._dist(target, x))
                remaining.remove(src2)
                
                loc_key = (label, round(target.cx / 40) * 40, round(target.cy / 40) * 40)
                self.history[loc_key] += 1

                # Permanent Phase 2 Logic: Always swap with a different item
                diff_item = self._get_closest_different_item(target, label, all_items_list)
                
                if diff_item:
                    # Execute exactly 2 actions. The items will touch and auto-merge, 
                    # preventing the 3rd drag from throwing the screen off.
                    return [
                        MergeAction(src1, diff_item, label, tier),
                        MergeAction(src2, diff_item, label, tier)
                    ]
                else:
                    # Fallback to direct merge if the board is entirely homogeneous or empty
                    return [
                        MergeAction(src1, target, label, tier),
                        MergeAction(src2, target, label, tier)
                    ]

        # Return empty list when no merges are left, which triggers the generator box in bot.py
        return []

    def _dist(self, a: DetectedItem, b: DetectedItem) -> float:
        return math.hypot(a.cx - b.cx, a.cy - b.cy)

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