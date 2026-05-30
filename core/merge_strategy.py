"""
MergeStrategy
=============
Decides which items to merge and in what order.
Higher-tier (rarer) items are prioritized.
"""

from dataclasses import dataclass
from typing import Optional
from core.screen_analyzer import DetectedItem, ScreenAnalyzer

# ── Item tier chains ───────────────────────────────────────────────────────────
# Each list = ascending merge tiers of one family.
# Add / edit to match the actual game items you've seen.

MERGE_CHAINS: dict[str, list[str]] = {
    "bcoin":     ["bcoin", "bcoin2"],
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
                f"grid({self.src.grid_row},{self.src.grid_col}) → "
                f"grid({self.dst.grid_row},{self.dst.grid_col})  "
                f"px({self.src.cx},{self.src.cy}) → "
                f"px({self.dst.cx},{self.dst.cy})")


class MergeStrategy:

    def plan(self, grid: dict[int, DetectedItem]) -> list[MergeAction]:
        from collections import defaultdict
        
        # 1. Group items by label
        by_label: dict[str, list[DetectedItem]] = defaultdict(list)
        for item in grid.values():
            by_label[item.label].append(item)

        actions = []
        
        # 2. Map all occupied cells to prevent dragging items on top of each other
        occupied = set((item.grid_row, item.grid_col) for item in grid.values())

        for label, items in by_label.items():
            # 3. Require at least 3 items to merge
            if len(items) < 3:
                continue
                
            tier      = LABEL_TIER.get(label, 0)
            remaining = list(items)
            
            # 4. Pull them together in groups of 3
            while len(remaining) >= 3:
                # Find the closest pair (Item A and our Anchor Item B)
                src1, target = self._closest_pair(remaining)
                remaining.remove(src1)
                remaining.remove(target)
                
                # Find the third item closest to Item B (Item C)
                src2 = min(remaining, key=lambda x: self._dist(target, x))
                remaining.remove(src2)
                
                # Check if A and B are already beside each other
                if self._dist(src1, target) == 1:
                    # They are adjacent! We only need 1 drag: Move C onto B.
                    actions.append(MergeAction(src2, target, label, tier))
                else:
                    # They are NOT adjacent. Find an empty spot next to B.
                    empty_spot = self._get_empty_neighbor(target.grid_row, target.grid_col, occupied)
                    
                    if empty_spot:
                        er, ec = empty_spot
                        
                        # Translate the empty grid cell back into physical mouse pixels
                        px = ScreenAnalyzer.GRID_ORIGIN_X + (ec * ScreenAnalyzer.CELL_W) + (ScreenAnalyzer.CELL_W // 2)
                        py = ScreenAnalyzer.GRID_ORIGIN_Y + (er * ScreenAnalyzer.CELL_H) + (ScreenAnalyzer.CELL_H // 2)
                        
                        virtual_dst = DetectedItem(label="empty_slot", cx=px, cy=py, grid_row=er, grid_col=ec, conf=1.0)
                        
                        # Drag A to the empty slot beside B
                        actions.append(MergeAction(src1, virtual_dst, label, tier))
                        
                        # Mark that empty slot as occupied so we don't double-stack it this cycle
                        occupied.add((er, ec))
                    else:
                        # Fallback: If B is totally surrounded by junk, just drag to target and let the game swap them
                        actions.append(MergeAction(src1, target, label, tier))
                        
                    # Finally, drag C onto B to complete the 3-merge
                    actions.append(MergeAction(src2, target, label, tier))

        # 5. Prioritize higher tier items first
        actions.sort(key=lambda a: -a.tier)
        return actions

    def best_action(self, grid) -> Optional[MergeAction]:
        acts = self.plan(grid)
        return acts[0] if acts else None

    def _dist(self, a: DetectedItem, b: DetectedItem) -> float:
        """
        Calculates distance based on GRID ADJACENCY, not pixels.
        Distance of 1 means they are immediate neighbors (Up/Down/Left/Right).
        """
        return abs(a.grid_row - b.grid_row) + abs(a.grid_col - b.grid_col)

    def _closest_pair(self, items):
        """Finds the two items closest to each other on the grid."""
        best_d, best = float("inf"), (items[0], items[1])
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                d = self._dist(items[i], items[j])
                if d < best_d:
                    best_d, best = d, (items[i], items[j])
                    # Optimization: If they are immediate neighbors, we can't get closer
                    if best_d == 1:
                        return best
        return best
        
    def _get_empty_neighbor(self, row, col, occupied) -> Optional[tuple[int, int]]:
        """Scans Up, Down, Left, and Right of the target for an empty grass tile."""
        for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            r, c = row + dr, col + dc
            # Ensure the coordinate is inside the game board bounds
            if 0 <= r < ScreenAnalyzer.GRID_ROWS and 0 <= c < ScreenAnalyzer.GRID_COLS:
                if (r, c) not in occupied:
                    return (r, c)
        return None