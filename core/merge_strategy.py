"""
MergeStrategy
=============
Decides which items to merge and in what order.
Higher-tier (rarer) items are prioritized.
"""

from dataclasses import dataclass
from typing import Optional
from core.screen_analyzer import DetectedItem


# ── Item tier chains ───────────────────────────────────────────────────────────
# Each list = ascending merge tiers of one family.
# Add / edit to match the actual game items you've seen.

# ── Item tier chains ───────────────────────────────────────────────────────────
# Each list = ascending merge tiers of one family.
# Add / edit to match the actual game items you've seen.

MERGE_CHAINS: dict[str, list[str]] = {
    "chick":  ["chick", "chick2", "chick3", "hen"],
    "cow":    ["calf",    "cow_1",   "cow_2",   "cow_3"],
    "goat":   ["goat",    "goat2",   "goat3",   "goat1"],
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
                f"grid({self.src.grid_row},{self.src.grid_col}) → "
                f"grid({self.dst.grid_row},{self.dst.grid_col})  "
                f"px({self.src.cx},{self.src.cy}) → "
                f"px({self.dst.cx},{self.dst.cy})")


class MergeStrategy:

    def plan(self, grid: dict[tuple, DetectedItem]) -> list[MergeAction]:
        from collections import defaultdict
        
        # 1. Check how many of every template exist and group them by label
        by_label: dict[str, list[DetectedItem]] = defaultdict(list)
        for item in grid.values():
            by_label[item.label].append(item)

        actions = []
        for label, items in by_label.items():
            # 2. We need at least 3 items to perform a valid merge
            if len(items) < 3:
                continue
                
            tier      = LABEL_TIER.get(label, 0)
            remaining = list(items)
            
            # 3. Pull them together in groups of 3
            while len(remaining) >= 3:
                # Find the closest pair (Item 1 and our Anchor Target)
                src1, target = self._closest_pair(remaining)
                remaining.remove(src1)
                remaining.remove(target)
                
                # Find the third item closest to our Anchor Target (Item 2)
                src2 = min(remaining, key=lambda x: self._dist(target, x))
                remaining.remove(src2)
                
                # Create the consecutive sequence: Drag Item 1 -> Target, then Drag Item 2 -> Target
                actions.append(MergeAction(src1, target, label, tier))
                actions.append(MergeAction(src2, target, label, tier))

        # 4. Prioritize higher tier items first. 
        # (We only sort by tier so that the sequence of 2 drags we planned above doesn't get shuffled)
        actions.sort(key=lambda a: -a.tier)
        return actions

    def best_action(self, grid) -> Optional[MergeAction]:
        acts = self.plan(grid)
        return acts[0] if acts else None

    def _dist(self, a: DetectedItem, b: DetectedItem) -> float:
        return ((a.cx - b.cx) ** 2 + (a.cy - b.cy) ** 2) ** 0.5

    def _closest_pair(self, items):
        best_d, best = float("inf"), (items[0], items[1])
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                d = self._dist(items[i], items[j])
                if d < best_d:
                    best_d, best = d, (items[i], items[j])
        return best