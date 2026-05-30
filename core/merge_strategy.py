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

MERGE_CHAINS: dict[str, list[str]] = {
    "chick":  ["chick_1", "chick_2", "chick_3", "hen",    "golden_hen"],
    "wheat":  ["wheat_1", "wheat_2", "wheat_3", "wheat_4"],
    "carrot": ["carrot_1","carrot_2","carrot_3","carrot_4"],
    "log":    ["log_1",   "log_2",   "log_3",   "log_4"],
    "gem":    ["gem_1",   "gem_2",   "gem_3",   "gem_4"],
    "coin":   ["coin_1",  "coin_2",  "coin_3",  "coin_4"],
    "cow":    ["calf",    "cow_1",   "cow_2",   "cow_3"],
    "goat":   ["goat1",   "goat2",   "goat3",   "goat4"],
    "flower": ["flower_1","flower_2","flower_3","flower_4"],
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
        by_label: dict[str, list[DetectedItem]] = defaultdict(list)
        for item in grid.values():
            by_label[item.label].append(item)

        actions = []
        for label, items in by_label.items():
            if len(items) < 2:
                continue
            tier      = LABEL_TIER.get(label, 0)
            remaining = list(items)
            while len(remaining) >= 2:
                src, dst = self._closest_pair(remaining)
                actions.append(MergeAction(src, dst, label, tier))
                remaining.remove(src)
                remaining.remove(dst)

        # Highest tier first; within same tier, closest pair first
        actions.sort(key=lambda a: (-a.tier, self._dist(a.src, a.dst)))
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
