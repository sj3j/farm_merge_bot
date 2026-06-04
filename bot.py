"""
Farm Merge Valley — PC Bot (Discord Edition)
=============================================
Controls Farm Merge Valley running as a Discord Activity.
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

import argparse
import time
import os
import cv2
from datetime import datetime

from core.window_controller import WindowController
from core.screen_analyzer   import ScreenAnalyzer
from core.merge_strategy    import MergeStrategy

# ── Default configuration ─────────────────────────────────────────────────────

CONFIG = {
    "loop_interval_sec":   1.0,   
    "merge_drag_duration": 0.4,   
    "merge_delay_sec":     0.15,  
    "box_click_delay_sec": 0.3,   
    "max_merges_per_cycle": 15,    
    "match_threshold":     0.84,
    "save_debug_frames":   False,
    "templates_dir":       "templates",
    
    # Generator Box Settings
    "generator_label":     "wooden_box", 
    "generator_taps":      50,           
    "generator_tap_delay": 0.15, 
    
    # Exclamation Box Settings
    "box_label":           "exclamation", 
    "box_taps":            1,             
    "box_tap_delay":       0.2,           

    # Multi-step Sequences (Trigger -> Step 1 -> Step 2 ...)
    "sequences": [
        {"trigger": "colcrystal2", "steps": ["green_colcrystal"]},
        {"trigger": "wrenchbox",  "steps": ["open"]},
        {"trigger": "wrenchbox2",  "steps": ["open"]}
    ],

    # Collectable Items
    "collect": ["colweaht", "colgroundweaht", "coldeadweaht",
                "colcarrot","colgroundcarrot", "coldeadcarrot",
                "colsoybean", "colgroundsoybean", "coldeadsoybean",
                "colsugarcane", "colgroundsugarcane", "coldeadsugarcane",
                "colchick","colgroundchick",
                "colcow", "colgroundcow",
                "colgoat", "colgroundgoat",
                "coldeadscoin", "checkmark",
                "colticket","green_collect"],
    
    # Popup Buttons (Clicked ONLY after opening an exclamation box)
    "popup_buttons": ["green_collect", "make", "close"]
}

class FarmMergeBot:
    def __init__(self, config: dict = None):
        self.cfg  = {**CONFIG, **(config or {})}
        self.ctrl     = WindowController()
        self.analyzer = ScreenAnalyzer(
            templates_dir  = self.cfg["templates_dir"],
            match_threshold= self.cfg["match_threshold"],
        )
        self.strategy = MergeStrategy()

        self.stats = {"cycles": 0, "merges": 0, "boxes": 0, "errors": 0}
        os.makedirs("logs",        exist_ok=True)
        os.makedirs("screenshots", exist_ok=True)

    def run(self, mode: str = "auto", max_cycles: int = 0):
        print(f"\n🤖  Farm Merge Bot  [mode={mode}]")
        print("    Move mouse to top-left corner to abort (PyAutoGUI failsafe)")
        print("    Press Ctrl+C to stop gracefully\n")
        self.ctrl.focus()

        try:
            while True:
                self.stats["cycles"] += 1
                n = self.stats["cycles"]
                print(f"── Cycle {n} ─────────────────────────────────")
                try:
                    # The screenshot is taken fresh inside the cycle now
                    self._cycle(mode)
                except Exception as e:
                    self.stats["errors"] += 1
                    print(f"  [!] Error: {e}")

                self._log_stats()
                if max_cycles and n >= max_cycles:
                    print("Max cycles reached.")
                    break
                time.sleep(self.cfg["loop_interval_sec"])

        except KeyboardInterrupt:
            print("\nStopped.")
            self._log_stats(final=True)

    def debug_once(self):
        frame  = self.ctrl.screenshot()
        items  = self.analyzer.analyze(frame)
        ann    = self.analyzer.debug_annotate(frame, items)
        path   = f"logs/debug_{datetime.now().strftime('%H%M%S')}.png"
        cv2.imwrite(path, cv2.cvtColor(ann, cv2.COLOR_RGB2BGR))
        print(f"[Debug] {len(items)} items detected → saved to {path}")

        grid   = self.analyzer.build_grid(items)
        groups = self.analyzer.find_merge_groups(grid)
        print(f"[Debug] {len(groups)} merge group(s):")
        for g in groups:
            coords = [(i.grid_row, i.grid_col) for i in g]
            print(f"  {g[0].label:15s}  ×{len(g)}  at grid cells {coords}")
            
        exclamations = [i for i in items if i.label == self.cfg["box_label"]]
        print(f"[Debug] {len(exclamations)} reward box(es) detected.")

    def _cycle(self, mode: str):
        if mode == "debug":
            self._do_debug(self.ctrl.screenshot())
            return

        # --- STEP 0: Initial Collection Sweep ---
        if mode in ("auto", "merge", "boxes"):
            self._collect_items(phase="Collect - Start")

        # --- STEP 1: Open Boxes ---
        if mode in ("auto", "boxes"):
            n = self._click_boxes(self.ctrl.screenshot())
            if n:
                time.sleep(1.0)

        # --- STEP 2: One Pass Merge Sweep (Loop Removed) ---
        if mode in ("auto", "merge"):
            merges_planned = self._do_merges(self.ctrl.screenshot())
            
            # --- STEP 3: Generator Tap Fallback ---
            # If 0 merges were planned on the board, hit the wooden box!
            if merges_planned == 0:
                self.strategy.clear_history() 
                self._click_generator(self.ctrl.screenshot())

            # --- STEP 4: Sequences ---
            time.sleep(0.5)
            self._run_sequences()

            # --- STEP 5: Final Collection Sweep ---
            time.sleep(0.5) 
            self._collect_items(phase="Collect - End")


    def _run_sequences(self) -> int:
        """Executes multi-step processes defined in CONFIG['sequences']."""
        sequences = self.cfg.get("sequences", [])
        if not sequences:
            return 0

        frame = self.ctrl.screenshot()
        items = self.analyzer.analyze(frame)
        total_executed = 0

        for seq in sequences:
            trigger_label = seq["trigger"]
            steps = seq["steps"]

            triggers = [item for item in items if item.label == trigger_label]

            for trigger in triggers:
                print(f"  [Sequence] Initiating '{trigger_label}' at ({trigger.cx},{trigger.cy})")
                self.ctrl.tap(trigger.cx, trigger.cy, delay=0.5)

                for step_label in steps:
                    time.sleep(1.0) 
                    step_frame = self.ctrl.screenshot()
                    step_items = self.analyzer.analyze(step_frame)

                    step_targets = [i for i in step_items if i.label == step_label]

                    if step_targets:
                        target = step_targets[0]
                        self.ctrl.tap(target.cx, target.cy, delay=0.5)
                        print(f"    ✓ Step successful: Clicked '{step_label}' at ({target.cx},{target.cy})")
                    else:
                        print(f"    [!] Step failed: Could not find '{step_label}'. Aborting sequence.")
                        break 
                
                total_executed += 1
                time.sleep(0.5) 

        return total_executed

    def _click_boxes(self, frame) -> int:
        """Finds 'exclamation' templates, taps below them, and handles popups."""
        items = self.analyzer.analyze(frame)
        box_label = self.cfg["box_label"]
        taps      = self.cfg["box_taps"]
        delay     = self.cfg["box_tap_delay"]
        
        boxes = [item for item in items if item.label == box_label]
        
        if boxes:
            print(f"  [Boxes] {len(boxes)} ready to open")
            for box in boxes:
                click_x = box.cx
                click_y = box.cy + 50  
                
                for _ in range(taps):
                    self.ctrl.tap(click_x, click_y, delay=delay)
                    self.stats["boxes"] += 1
                    
                print(f"    ✓ Tapped reward at ({click_x},{click_y})")

                time.sleep(1.0) 
                popup_frame = self.ctrl.screenshot()
                popup_items = self.analyzer.analyze(popup_frame)
                
                for popup_label in self.cfg.get("popup_buttons", []):
                    btns = [i for i in popup_items if i.label == popup_label]
                    for btn in btns:
                        self.ctrl.tap(btn.cx, btn.cy, delay=0.5)
                        print(f"    ✓ Clicked popup button '{popup_label}'")
                
        return len(boxes)
    
    def _collect_items(self, phase="Collect") -> int:
        """Scans the board and clicks collectable items once per call."""
        collect_list = self.cfg.get("collect", [])
        total_collected = 0
        
        frame = self.ctrl.screenshot()
        items = self.analyzer.analyze(frame)
        targets = [item for item in items if item.label in collect_list]
        
        if targets:
            for item in targets:
                self.ctrl.tap(item.cx, item.cy, delay=0.2)
                total_collected += 1
                print(f"    ✓ Picked up '{item.label}' at ({item.cx},{item.cy})")
            
            time.sleep(0.5) 
            print(f"  [{phase}] Done! Collected {total_collected} items this pass.")
            
        return total_collected

    def _click_generator(self, frame):
        """Finds the generator box template and rapid-taps it to spawn items."""
        items = self.analyzer.analyze(frame)
        gen_label = self.cfg["generator_label"]
        taps      = self.cfg["generator_taps"]
        
        boxes = [item for item in items if item.label == gen_label]
        
        if boxes:
            box = boxes[0] 
            print(f"  [Generator] No merges left! Tapping '{gen_label}' {taps} times at ({box.cx},{box.cy})...")
            
            for _ in range(taps):
                self.ctrl.tap(box.cx, box.cy, delay=self.cfg["generator_tap_delay"])
                self.stats["boxes"] += 1
                
            print("  [Generator] Done tapping. Waiting for items to spawn.")

    def _do_merges(self, frame) -> int:
        """Executes one pass of planned merges (continuous loop removed)."""
        limit   = self.cfg["max_merges_per_cycle"]
        items   = self.analyzer.analyze(frame)
        grid    = self.analyzer.build_grid(items)
        actions = self.strategy.plan(grid)

        if not actions:
            return 0

        print(f"  [Merge] {len(items)} items  |  {len(actions)} actions planned")

        for i, act in enumerate(actions[:limit]):
            print(f"    [{i+1}] {act}")
            self.ctrl.drag_item(
                act.src.cx, act.src.cy,
                act.dst.cx, act.dst.cy,
                duration = self.cfg["merge_drag_duration"],
                delay    = self.cfg["merge_delay_sec"],
            )
            self.stats["merges"] += 1

        if self.cfg["save_debug_frames"] and items:
            ann  = self.analyzer.debug_annotate(frame, items)
            path = f"logs/frame_{datetime.now().strftime('%H%M%S%f')}.png"
            cv2.imwrite(path, cv2.cvtColor(ann, cv2.COLOR_RGB2BGR))
            
        return len(actions)

    def _do_debug(self, frame):
        items = self.analyzer.analyze(frame)
        ann   = self.analyzer.debug_annotate(frame, items)
        path  = f"logs/debug_{datetime.now().strftime('%H%M%S%f')}.png"
        cv2.imwrite(path, cv2.cvtColor(ann, cv2.COLOR_RGB2BGR))
        print(f"  [Debug] {len(items)} items → {path}")

    def _log_stats(self, final: bool = False):
        s = self.stats
        tag = "Final" if final else "Stats"
        print(f"  [{tag}] cycles={s['cycles']}  merges={s['merges']}  "
              f"boxes={s['boxes']}  errors={s['errors']}")

def main():
    p = argparse.ArgumentParser(description="Farm Merge Valley Bot (Discord)")
    p.add_argument("--mode",     choices=["auto","merge","boxes","debug"], default="auto")
    p.add_argument("--interval", type=float, default=1.0, help="Seconds between cycles")
    p.add_argument("--cycles",   type=int,   default=0, help="Max cycles (0 = unlimited)")
    p.add_argument("--debug-once", action="store_true", help="Detect items once, save annotated image, exit")
    args = p.parse_args()

    print("\n[Bot] Starting in 5 seconds... Please switch to the Discord window now!")
    time.sleep(5)

    cfg = {**CONFIG, "loop_interval_sec": args.interval}
    bot = FarmMergeBot(config=cfg)

    if args.debug_once:
        bot.debug_once()
    else:
        bot.run(mode=args.mode, max_cycles=args.cycles)

if __name__ == "__main__":
    main()