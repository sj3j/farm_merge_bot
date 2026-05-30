# 🤖 Farm Merge Valley — Discord Bot

Controls Farm Merge Valley running as a **Discord Activity** directly from your PC.

---

## Install

```bash
pip install -r requirements.txt
```

---

## Setup (one time only)

### Step 1 — Select the game region inside Discord

```bash
python select_region.py
```

A full-screen overlay appears. **Drag a rectangle over ONLY the game area** inside Discord.
Press **Enter** to confirm. Saved to `config/region.json`.

```
┌──────────────── Discord ─────────────────┐
│  sidebar  │  ┌──────────────────┐        │
│           │  │  drag here ✓     │        │
│           │  │  (game only)     │        │
│           │  └──────────────────┘        │
└──────────────────────────────────────────┘
```

### Step 2 — Capture item sprites

```bash
python capture_templates.py
```

- Left click → top-left of item
- Right click → bottom-right → type label → Enter
- S = refresh screenshot, Q = quit

Label names: `chick_1`, `chick_2`, `hen`, `wheat_1`, `wheat_2`, `log_1`, `chest`, `calf`, `cow_1` ...

---

## Run

```bash
python bot.py                  # full auto
python bot.py --debug-once     # test detection, no clicks
python bot.py --mode merge     # only merge
python bot.py --mode boxes     # only click boxes
python bot.py --interval 3     # slower loop
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot clicks wrong spot | Re-run `select_region.py` |
| Items not detected | Lower threshold to 0.65 in `screen_analyzer.py` |
| Wrong grid positions | Tune `GRID_ORIGIN_X/Y` and `CELL_W/H` |

**Failsafe**: move mouse to top-left corner of screen → bot stops instantly.
