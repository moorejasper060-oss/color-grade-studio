# Color Grade Studio — agent instructions

Windows desktop app for fast video color grading: load a clip, pick one of 20 preset looks,
fine-tune with 5 sliders (exposure/contrast/saturation/temperature/tint), trim, export. Real
3D-LUT pipeline (`.cube` input + creative LUTs), 10-bit-aware for log footage (D-Log M,
S-Log3, V-Log). Python + PySide6 + OpenCV/NumPy + FFmpeg; PyInstaller for the exe.

## Session start

Jasper's coding agents share persistent project memory at
`~/.claude/projects/-Users-jaspermoore/memory/` (index: `MEMORY.md`). Check it for a state doc
for this project; if you do substantial work here, maintain one (absolute dates). Standing
rule: **always commit AND push code changes automatically.**

## Run / build / test

- Run from source: `pip install -r requirements.txt` then `python -m color_grade_studio`.
  FFmpeg + ffprobe must be on PATH (export AND the e2e tests need them).
- Tests: `pip install -r requirements-dev.txt` then `python -m pytest`
  (src layout — pytest config sets `pythonpath=src`; run from repo root).
- Windows exe: `python build_exe.py` (add `--onefile` for single-exe) →
  `dist/ColorGradeStudio/ColorGradeStudio.exe`. Windows-only; it bundles whatever
  ffmpeg.exe/ffprobe.exe are on PATH (logs their SHA-256) — pin a known FFmpeg release for
  distribution builds. Exe is unsigned → SmartScreen warning.
- No CI — everything is local.

## Architecture rules

- `src/color_grade_studio/core/` is deliberately PURE (no Qt, no globals) and unit-tested
  against synthetic frames — keep transforms side-effect-free.
- LUT stacking order is fixed and baked into one combined LUT so preview == export:
  input LUT → creative LUT → preset → manual sliders. Don't reorder.
