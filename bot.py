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
from core.box_clicker       import BoxClicker

# ── Default configuration ─────────────────────────────────────────────────────

# ── Default configuration ─────────────────────────────────────────────────────

CONFIG = {
    "loop_interval_sec":   2.0,
    "merge_drag_duration": 1.2,   # INCREASED: Forces a slower drag so the game registers it
    "merge_delay_sec":     0.5,
    "box_click_delay_sec": 0.5,   # INCREASED: Slight pause when clicking boxes
    "max_merges_per_cycle":6,
    "match_threshold":     0.84,  # INCREASED: Filters out false positives (must be 88% match)
    "save_debug_frames":   False,
    "templates_dir":       "templates",
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
        self.clicker  = BoxClicker(self.ctrl, self.analyzer)

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

        boxes  = self.clicker.find_ready_boxes(frame)
        print(f"[Debug] {len(boxes)} ready box(es) detected: {boxes}")

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
            self._do_merges(frame)

    def _click_boxes(self, frame) -> int:
        boxes = self.clicker.find_ready_boxes(frame)
        print(f"  [Boxes] {len(boxes)} ready")
        for cx, cy in boxes:
            self.ctrl.tap(cx, cy, delay=self.cfg["box_click_delay_sec"])
            self.stats["boxes"] += 1
            print(f"    ✓ ({cx},{cy})")
        return len(boxes)

    def _do_merges(self, frame):
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

    # Wait for the user to tab into Discord *after* printing
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