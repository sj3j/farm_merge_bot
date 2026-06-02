# core/merge_strategy.py

import math
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
from core.screen_analyzer import DetectedItem

# levels are to 3: The bot will now recognize and merge up to level 3 crops
MERGE_CHAINS: dict[str, list[str]] = {
    "weaht":     ["weaht", "weaht2", "weaht3"],
    "carrot":    ["carrot", "carrot2", "carrot3"],
    "sugarcane": ["sugarcane", "sugarcane2", "sugarcane3"],
    "soybean":   ["soybean", "soybean2", "soybean3"],
    "chick":     ["chick", "chick2", "chick3"],
    "cow":       ["cow", "cow2", "cow3"],
    "goat":      ["goat", "goat2", "goat3"],
    "pig":       ["pig", "pig2", "pig3"],
    "wrench":    ["wrench", "wrench2", "wrench3", "wrench4", "wrench5", "wrench6"],
    "box":       ["box", "box2", "box3", "box4"],
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
        # 0. Deduplicate overlapping items AND FILTER UNMERGEABLE ITEMS
        unique_items = []
        for item in grid.values():
            if item.label not in LABEL_TIER:
                continue
                
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
        
        # Keep track of objects we cannot swap with (dead crops, coins, etc)
        unswappable_items = [i for i in grid.values() if i.label not in LABEL_TIER]

        # 3. Process exactly ONE group at a time
        for label in labels_by_priority:
            items = by_label[label]
            if len(items) < 3:
                continue
                
            tier = LABEL_TIER.get(label, 0)
            
            # Determine merge size: Priority 5, fallback to 3
            k = 5 if len(items) >= 5 else 3
            
            # Find the tightest cluster of K items to minimize drag distance
            best_cluster = None
            best_dist = float('inf')
            
            for potential_target in items:
                others = sorted([i for i in items if i != potential_target], key=lambda x: self._dist(potential_target, x))
                cluster_others = others[:k-1]
                
                dist_sum = sum(self._dist(potential_target, x) for x in cluster_others)
                if dist_sum < best_dist:
                    best_dist = dist_sum
                    best_cluster = (potential_target, cluster_others)
            
            target, same_label_items = best_cluster
            
            setup_items = same_label_items[:-1] 
            trigger_item = same_label_items[-1] 
            k_group = [target] + same_label_items
            
            # --- EXACT ADJACENT CELL TARGETING ---
            # Instead of looking for random crops, calculate the 8 grid spots exactly around the target.
            offsets = [
                (0, -80), (0, 80), (-95, 0), (95, 0),
                (-95, -80), (95, -80), (-95, 80), (95, 80)
            ]
            
            valid_destinations = []
            for dx, dy in offsets:
                nx, ny = target.cx + dx, target.cy + dy
                
                # Check 1: Is there a dead crop/coin blocking this spot?
                if any(math.hypot(nx - u.cx, ny - u.cy) < 40 for u in unswappable_items):
                    continue
                # Check 2: Is one of our own group items already sitting here?
                if any(math.hypot(nx - s.cx, ny - s.cy) < 40 for s in k_group):
                    continue
                    
                # The spot is safe (either empty or has a swappable crop)
                valid_destinations.append(DetectedItem(label="adjacent_space", cx=nx, cy=ny, confidence=1.0))
            
            loc_key = (label, round(target.cx / 40) * 40, round(target.cy / 40) * 40)
            self.history[loc_key] += 1
            
            actions = []
            dest_index = 0
            
            # Phase 1: Move setup items to adjacent spots
            for src in setup_items:
                # INTELLIGENCE UPGRADE: If the item is ALREADY adjacent to the target, leave it alone!
                if self._dist(src, target) < 130:
                    continue
                    
                if dest_index < len(valid_destinations):
                    dst = valid_destinations[dest_index]
                    actions.append(MergeAction(src, dst, label, tier))
                    dest_index += 1
                else:
                    # Failsafe if surrounded by map edges
                    actions.append(MergeAction(src, target, label, tier))
                    
            # Phase 2: Drag the trigger item directly onto the target to execute the merge
            actions.append(MergeAction(trigger_item, target, label, tier))
            
            return actions

        return []

    def _dist(self, a: DetectedItem, b: DetectedItem) -> float:
        return math.hypot(a.cx - b.cx, a.cy - b.cy)