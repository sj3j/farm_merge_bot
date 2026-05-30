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

# ── Default configuration ─────────────────────────────────────────────────────

CONFIG = {
    "loop_interval_sec":   2.0,
    "merge_drag_duration": 1.2,
    "merge_delay_sec":     0.5,
    "box_click_delay_sec": 0.5,
    "max_merges_per_cycle":6,
    "match_threshold":     0.84,
    "save_debug_frames":   False,
    "templates_dir":       "templates",
    
    # Generator Box Settings
    "generator_label":     "wooden_box", 
    "generator_taps":      10,           
    "generator_tap_delay": 0.15, 
    
    # Exclamation Box Settings
    "box_label":           "exclamation", 
    "box_taps":            1,             
    "box_tap_delay":       0.2,           

    # NEW: Collectable Items (Clicked once at the end of the cycle)
    "collect": ["colcarrot", "colticket", "colchick", "colcow", "colgoat", "colsoybean", "colsugarcane", "colweaht", "colgroundweaht", "colgroundcarrot", "colgroundchick", "colgroundcow", "colgroundgoat", "colgroundsoybean", "colgroundsugarcane", "checkmark"],
    
    # NEW: Popup Buttons (Clicked ONLY after opening an exclamation box)
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
                    frame = self.ctrl.screenshot()
                    self._cycle(frame, mode)
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

    def _cycle(self, frame, mode: str):
        if mode == "debug":
            self._do_debug(frame)
            return

        if mode in ("auto", "boxes"):
            n = self._click_boxes(frame)
            if n:
                time.sleep(1.2)
                frame = self.ctrl.screenshot()

        if mode in ("auto", "merge"):
            merges_planned = self._do_merges(frame)
            
            # If 0 merges are planned (or all are blacklisted), hit the wooden box!
            if merges_planned == 0:
                self.strategy.clear_history() 
                self._click_generator(frame)

            # --- COLLECT: Keep scanning and collecting until the board is clear ---
            time.sleep(1) 
            self._collect_items()
            # ----------------------------------------------------------------------

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
                # Tap the box BELOW the exclamation mark
                click_x = box.cx
                click_y = box.cy + 50  
                
                for _ in range(taps):
                    self.ctrl.tap(click_x, click_y, delay=delay)
                    self.stats["boxes"] += 1
                    
                print(f"    ✓ Tapped reward at ({click_x},{click_y})")

                # --- POPUP LOGIC: Only happens here, not on wooden boxes ---
                time.sleep(1.0) # Wait for the popup animation to finish
                popup_frame = self.ctrl.screenshot()
                popup_items = self.analyzer.analyze(popup_frame)
                
                for popup_label in self.cfg.get("popup_buttons", []):
                    btns = [i for i in popup_items if i.label == popup_label]
                    for btn in btns:
                        self.ctrl.tap(btn.cx, btn.cy, delay=0.5)
                        print(f"    ✓ Clicked popup button '{popup_label}'")
                # -----------------------------------------------------------
                
        return len(boxes)
    
    def _collect_items(self) -> int:
        """Scans the board and clicks collectable items until none are left."""
        collect_list = self.cfg.get("collect", [])
        total_collected = 0
        
        while True:
            # Take a fresh screenshot for every pass
            frame = self.ctrl.screenshot()
            items = self.analyzer.analyze(frame)
            
            # Filter for items that are in your collect list
            targets = [item for item in items if item.label in collect_list]
            
            # If no collectable items are found, break the loop and move on!
            if not targets:
                break 
                
            for item in targets:
                self.ctrl.tap(item.cx, item.cy, delay=0.25)
                total_collected += 1
                print(f"    ✓ Picked up '{item.label}' at ({item.cx},{item.cy})")
            
            # Wait a moment for the game animations to finish and items to settle
            # before taking the next screenshot
            time.sleep(1.0) 
            
        if total_collected > 0:
            print(f"  [Collect] Done! Collected {total_collected} items this cycle.")
            
        return total_collected

    def _click_generator(self, frame):
        """Finds the generator box template and rapid-taps it to spawn items."""
        items = self.analyzer.analyze(frame)
        gen_label = self.cfg["generator_label"]
        taps      = self.cfg["generator_taps"]
        
        boxes = [item for item in items if item.label == gen_label]
        
        if boxes:
            box = boxes[0] # Target the first generator found
            print(f"  [Generator] No merges left! Tapping '{gen_label}' {taps} times at ({box.cx},{box.cy})...")
            
            for _ in range(taps):
                self.ctrl.tap(box.cx, box.cy, delay=self.cfg["generator_tap_delay"])
                self.stats["boxes"] += 1
                
            print("  [Generator] Done tapping. Waiting for items to spawn.")

    def _do_merges(self, frame) -> int:
        items   = self.analyzer.analyze(frame)
        grid    = self.analyzer.build_grid(items)
        actions = self.strategy.plan(grid)
        limit   = self.cfg["max_merges_per_cycle"]

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
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between cycles")
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