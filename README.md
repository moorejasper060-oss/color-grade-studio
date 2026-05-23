# Color Grade Studio

A Windows desktop app for fast video color grading. Load a clip, pick a look
from 20 preset styles, fine-tune with five intuitive sliders, trim, and export.

Built with Python · PySide6 · OpenCV · FFmpeg.

---

## Features

- **20 built-in color grade presets** (plus an "Original" pass-through) —
  Cinematic, Teal & Orange, Vintage, Bleach Bypass, Day for Night,
  Cross Process, Anamorphic, Sepia, B&W, B&W High Contrast, Warm, Cool,
  Vibrant, Punch, Golden Hour, Sunset, Clean & Crisp, Pastel, Moody,
  Faded Film.
- **Live preview** — see the grade applied to your clip in real time.
- **Manual adjustments** — exposure, contrast, saturation, temperature, tint.
- **Before/after compare** — hold the `B` key (or click the toggle) to peek at
  the original.
- **Trim** — drag two handles on the timeline to set in/out points.
- **Export video** — H.264 MP4 with audio preserved, quality presets from
  visually-lossless to small-file.
- **Export photo** — save the current frame as JPG or PNG with the grade baked
  in.
- **Drag & drop** support for opening videos.
- **Bundles FFmpeg** — the Windows distribution ships with its own FFmpeg, so
  it works out of the box.

## Supported formats

MP4, MOV, AVI, MKV, WebM, M4V (anything FFmpeg + OpenCV can read).
Output is always H.264 MP4 for maximum compatibility.

---

## Quick start (from source)

```powershell
git clone https://github.com/moorejasper060-oss/color-grade-studio.git
cd color-grade-studio

python -m pip install -r requirements.txt
python -m color_grade_studio
```

You need FFmpeg on your `PATH` for video export to work:

```powershell
winget install Gyan.FFmpeg
```

Open `File ▸ Open video…` (or drop a video onto the window), pick a look from
the **Look** column, dial in any adjustments, drag the timeline handles to
trim, then `File ▸ Export video…`.

## Build the .exe

```powershell
python -m pip install -r requirements-dev.txt
python build_exe.py
```

The launcher will be at `dist/ColorGradeStudio/ColorGradeStudio.exe` along
with a bundled FFmpeg. Pass `--onefile` for a single-exe build (slower first
launch). The whole folder is portable — copy it anywhere and the `.exe`
will run.

**About the bundled FFmpeg.** `build_exe.py` copies whichever `ffmpeg.exe` and
`ffprobe.exe` are on the build machine's `PATH` and prints their SHA-256 to
the build log. Pin to a known release (e.g. the Gyan build via winget) on the
build host before producing distribution artifacts.

**About SmartScreen.** The shipped `.exe` is **not code-signed**, so Windows
will show a "Windows protected your PC" warning the first time you run it.
Click "More info" → "Run anyway". Sign with an EV/OV certificate before
distributing to other people.

## Run the tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

End-to-end tests render synthetic FFmpeg clips and verify the export
pipeline produces playable MP4 output, that cancelled exports clean up
their partial files, and that a failed ffmpeg run leaves no zero-byte
junk behind. FFmpeg must be on `PATH` for these to run.

---

## Architecture

```
src/color_grade_studio/
├── core/
│   ├── color_engine.py   Pure-function image transforms (numpy + OpenCV)
│   ├── presets.py        The 20 named looks
│   ├── video_io.py       VideoSource wrapper + FFmpeg discovery
│   └── export.py         Background ExportJob that pipes frames to FFmpeg
├── ui/
│   ├── main_window.py    Top-level QMainWindow
│   ├── preview_widget.py Frame display with before/after toggle
│   ├── timeline_widget.py Custom timeline with trim handles + playhead
│   ├── preset_panel.py   Scrollable list of preset thumbnails
│   ├── adjustments_panel.py 5 manual sliders
│   ├── transport_controls.py Play/Pause, Before/After, photo export
│   ├── export_dialog.py  Export options + threaded progress
│   └── styles.py         Dark theme stylesheet
└── main.py               QApplication entry point
```

The color engine is pure — no Qt, no globals — so every preset and every
slider combination is unit-tested against a synthetic test frame.

## Keyboard shortcuts

| Key                 | Action                          |
|---------------------|---------------------------------|
| `Ctrl+O`            | Open a video                    |
| `Ctrl+E`            | Export video                    |
| `Ctrl+Shift+E`      | Save current frame as photo     |
| `Space`             | Play / pause                    |
| `B` (hold)          | Show original (before)          |

## License

MIT — see [LICENSE](LICENSE).
