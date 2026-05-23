# Color Engine v2 — Professional-Grade Presets

**Date:** 2026-05-23
**Status:** Approved (Jasper, "B but you can additionally try to copy other luts")
**Author:** Claude (Opus 4.7)

## Problem

The 10 cinematic presets shipped on 2026-05-23 are tuned correctly *for what the engine can do*, but the engine itself is limited to global, single-axis transforms (exposure, WB, BGR lift/gamma/gain, contrast, saturation, hue). As Jasper observed:

- **"Day for Night just looks blue"** — a global `temperature=-0.40` paints the whole frame cool. Real day-for-night puts blue *only* in highlights (sky), crushes shadows toward near-black, desaturates skin, and adds a faint magenta cast to deep shadows. My engine has no way to express "blue *here* but not *there*."
- **"All of them look quite simple"** — every preset can only *tilt* the global color balance. There's no way to lift shadow saturation while crushing highlight saturation, no way to shift shadow hue independently of midtone hue, no tone-curve toe/shoulder shaping, no halation.

Professional film looks use a different toolkit: 3-way color (shadows/mids/highlights each get their own hue+sat shift), tone curves with shaped toe/shoulder, saturation curves by luminance, and halation. The presets need these to feel "professional grade."

## Goals

1. **Extend the engine** with the missing professional tools — but additively, so the existing GradeParams keep working.
2. **Profile free reference LUTs** as ground-truth targets — measure what they actually do per zone, then dial in my params to match.
3. **Retune all 10 presets** using the new vocabulary. Each preset should look meaningfully more sophisticated than the v1 version.
4. **Preserve the LUT pipeline** — the new transforms get baked into the combined LUT just like the old ones, so preview and export stay pixel-identical and 10-bit export keeps working.

## Non-goals

- **No new file formats.** Presets stay `GradeParams` instances; the existing LUT-loading UI is unchanged.
- **No commercial LUT redistribution.** Free reference LUTs are used as design targets only — profile them, then write our own params that produce a similar look.
- **No grain.** Halation yes (cheap convolution), grain no (would need per-frame noise, not a LUT-bake-able transform).
- **No per-frame analysis.** Everything operates on color alone, so the whole transform stays expressible as a 3D LUT.

## New tools added to the engine

Each is a new optional field on `GradeParams`, with a sensible default that's a no-op (so v1 presets keep working).

### 1. Three-way HSL color (`shadows_hsl`, `midtones_hsl`, `highlights_hsl`)

Three new fields, each a `(hue_shift_deg, sat_mult, lum_mult)` tuple, default `(0.0, 1.0, 1.0)` (no-op).

Math: build a per-pixel luminance mask for each zone (shadows: 0–0.33 with smooth falloff; midtones: 0.15–0.85; highlights: 0.67–1.0). Convert the frame to HSV, apply the per-zone shifts weighted by the mask, convert back. This is exactly how DaVinci's three-way wheels work.

**Why this matters**: lets *Day for Night* put cool blue in highlights, near-black in shadows, faint magenta in deep shadows — all independently.

### 2. Tone curve (`tone_curve`)

A `Tuple[float, float, float, float, float]` of 5 control points: `(black_out, lo_mid_out, mid_out, hi_mid_out, white_out)`. Default `(0.0, 0.25, 0.5, 0.75, 1.0)` is the identity. Inputs are at fixed positions 0.0, 0.25, 0.5, 0.75, 1.0; the function builds a 256-entry lookup table via monotonic Catmull-Rom interpolation through the control points and applies it via `cv2.LUT` (numpy-only, no scipy dependency).

**Why this matters**: lets you push midtones up while keeping highlights flat (the classic "lifted blacks + rolled-off whites" cinematic look). The S-curve baked from `contrast` is too symmetric to do this well.

### 3. Saturation by luminance (`luma_sat`)

A `Tuple[float, float, float]` of `(sat_shadows, sat_mids, sat_highlights)` multipliers. Default `(1.0, 1.0, 1.0)` (no-op).

Math: piecewise saturation multiplier indexed by per-pixel luminance. Smooth weighted blend at the boundaries.

**Why this matters**: "vibrance" — punchy mids without oversaturated skies/skin. Modern film looks crush shadow saturation to zero (everything dark goes monochrome) while bumping mid saturation.

### 4. Halation (`halation`)

A scalar `0.0 – 1.0` (default `0.0`). Applies a Gaussian-blurred bright red mask additively to highlights, simulating the way light-struck film scatters red into surrounding pixels.

**Why this matters**: signature of film stock — Kodak Vision3 vs digital is largely about halation. Adding it makes *Vintage Print* feel like real film, not a desat filter.

## Pipeline order (revised)

Applied to float32 BGR in [0, 1]:

```
exposure → white_balance → tone_curve → lift_gamma_gain → contrast
  → three_way_hsl → luma_sat → saturation → hue_shift
  → halation → fade → vignette
```

Order matters: tone curve runs *before* lift/gamma/gain so the LGG operates on the toned image; three_way_hsl runs after contrast so the zone masks are stable; halation runs late so the bloom uses the final highlight values.

## Reference-LUT profiling tool

New file: `tools/profile_lut.py`.

Takes a `.cube` file as input. Applies the LUT to a known set of test patches (gray ramp, skin tone, sky, foliage, primary colors, neutral shadows, neutral highlights). Outputs measured per-zone shifts that can be pasted directly into a `GradeParams`:

```
$ python tools/profile_lut.py refs/teal_orange_blockbuster.cube
shadows_hsl:    (h=+8°, s=1.20, l=0.95)
midtones_hsl:   (h=+2°, s=1.10, l=1.00)
highlights_hsl: (h=-12°, s=1.15, l=1.03)
tone_curve:     (0.04, 0.20, 0.52, 0.78, 0.98)
luma_sat:       (0.85, 1.18, 1.05)
overall: exposure=+0.05, contrast=+0.22, saturation=+0.10
```

This is the tuning tool. For each of the 10 presets I'll find one or two free reference LUTs that match the target look, profile them, and either copy the values directly or tweak them.

The reference LUTs themselves are NOT shipped. They live in `~/Downloads/` or a local `refs/` folder gitignored. Only the resulting `GradeParams` go into the repo.

## Architecture changes

- `src/color_grade_studio/core/color_engine.py` — add four new `_transform()` helpers, extend `GradeParams` with four new fields, update `_grade_float_bgr` pipeline.
- `src/color_grade_studio/core/presets.py` — retune all 10 presets using the new vocabulary.
- `src/color_grade_studio/core/__init__.py` — no change (new types are nested inside `GradeParams`).
- `tools/profile_lut.py` — new file. Standalone CLI tool, not imported by the app.
- `.gitignore` — add `refs/` so downloaded reference LUTs don't get committed.
- `tests/test_color_engine.py` — add tests for each new transform (3-way HSL, tone curve, luma sat, halation) and tighten existing preset signature tests where the new tools let us assert more (e.g., *Day for Night* shadows should be near-black AND highlights blue).

## Backwards compatibility

The four new fields all default to no-op values. Any existing `GradeParams(exposure=0.5, ...)` produces bit-identical output before and after. The LUT pipeline, export, UI tooltips — all untouched.

## Testing strategy

- **New per-transform unit tests** (5+): verify each new transform alone does what it claims (e.g., three_way_hsl with `shadows_hsl=(0, 0, 0)` zeros shadow saturation; tone_curve with `(0.0, 0.1, 0.3, 0.6, 0.9)` darkens midtones).
- **Existing preset signature tests** remain. Where the new tools enable stricter assertions, tighten the test (e.g., *Day for Night* shadows must be < 30 and highlights mean_b > mean_r).
- **End-to-end LUT bake test** stays — the combined LUT must still produce the same output as direct application of the (now extended) pipeline.
- **Manual visual check** post-build, same as before.

## Risks

1. **Tuning rabbit hole.** Profiling 10+ LUTs and dialing in matching params could absorb time. Mitigation: time-box per preset to ~30 minutes; if I can't match a reference well, ship a "good enough" version and note in a comment.
2. **Three-way zone masks have rough edges.** If the zone thresholds aren't smooth, you'll see banding where shadow turns into midtone. Mitigation: use smooth sigmoid masks, not hard thresholds.
3. **Halation is easy to overdo.** A weak default and a `0.0` baseline on most presets means it can only enhance, not ruin. Vintage Print and Cinematic get the smallest non-zero values.
4. **Performance.** 4 new transforms per frame on a 1280-wide preview. At 30 fps that's ~33 ms budget. Conservative numpy will hit it; if not, drop preview resolution to 960w.

## Out of scope (future work)

- Grain
- Hue-vs-hue (rotate oranges separate from reds)
- Custom user presets / save current grade
- Bundled reference LUTs (license thicket; user can already load any LUT via the existing UI)

## References

- [DaVinci Resolve three-way color grading](https://documentation.blackmagicdesign.com/UserManuals/DaVinciResolve19/Color/Color_3WayCorrectors.htm)
- [Halation explanation (LightIron)](https://lightiron.com/news/halation-in-film/)
- [Free LUTs from Color Grading Central](https://www.colorgradingcentral.com/free-luts/)
- [Free Cinematic LUTs (FilterGrade)](https://filtergrade.com/free-cinematic-luts-video-editing/)
- [99+ LUTs Cinematic Color Grading Pack (IWLTBAP)](https://luts.iwltbap.com/)
- [Tone curves in colour grading (No Film School)](https://nofilmschool.com/iconic-film-color-grades)
