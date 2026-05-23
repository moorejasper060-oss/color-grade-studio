# Cinematic Presets — Design Spec

**Date:** 2026-05-23
**Status:** Approved (verbal — Jasper "Looks good", 2026-05-23)
**Author:** Claude (Opus 4.7) for Jasper Moore

## Problem

The app currently ships 20 generic presets — a mix of cinematic looks
(*Cinematic*, *Teal & Orange*, *Vintage*) and basic tonal shifts (*Warm*,
*Cool*, *Vibrant*, *Punch*, *Pastel*, *Clean & Crisp*, etc.). For a D-Log M /
drone + tennis-school workflow, the basic tonal shifts add noise without
adding value — they're just slider sweeps you can do with the manual controls.

The user wants **fewer, better presets — all unmistakably cinematic.**

## Goals

1. Replace the 20 presets with **exactly 10 cinematic looks**, each tied to
   a specific iconic film reference so the user knows what they're picking.
2. Each preset should be **awesome on its own** — looking at the
   thumbnail/preview should make it obvious which film/genre the look
   evokes.
3. Tune each preset against a **free reference LUT** so the math behaves
   like a real cinematic grade, not a guess.
4. Keep the existing architecture intact — the LUT pipeline, the
   combined-LUT export, the 10-bit handling, the slider behaviour all
   stay the same. Only `presets.py` changes.

## Non-goals

- **No bundled commercial LUTs.** Free reference LUTs are used for tuning
  only; the shipped presets are programmatic `GradeParams`. No
  redistribution, no licence problem.
- **No new preset format.** Presets stay as `GradeParams` so the existing
  pipeline (`compute_combined_lut`, `apply_pipeline`, ffmpeg `lut3d`
  filter) keeps working.
- **No grain / no film-stock physical simulation.** Halation, grain,
  bloom are out of scope for this pass — too much new code for marginal
  payoff on a phone-edit-focused workflow.
- **No backwards-compat for old preset IDs.** There are no saved-project
  files to break. Old IDs will simply not resolve.

## The 10 cinematic presets

| # | ID | Display name | Reference look | Signature |
|---|------|------|------|------|
| 1 | `cinematic` | Cinematic | Netflix originals, Marvel | Modern default. Teal in shadows, warm highlights, soft S-curve contrast, lifted blacks. |
| 2 | `teal_orange` | Teal & Orange | Mad Max: Fury Road | Aggressive complementary push. Strong saturation, deep cyan shadows, bright orange skin. |
| 3 | `moody_drama` | Moody Drama | Joker, Sicario | Low-key, desaturated, cool shadow tint, rolled-off highlights. -0.1 exposure baseline. |
| 4 | `bleach_bypass` | Bleach Bypass | Saving Private Ryan, Three Kings | Silver-halide. Crushed blacks, low saturation, hard contrast. |
| 5 | `golden_hour` | Golden Hour | Knives Out, La La Land sunset | Warm rolled-off highlights, magic-hour glow, slight fade. |
| 6 | `anamorphic_dream` | Anamorphic Dream | Drive, Atomic Blonde | Soft cyan highlights, slight magenta shadows, gentle vignette. |
| 7 | `vintage_print` | Vintage Print | Killers of the Flower Moon | Kodak Vision3 emulation. Lifted blacks, warm cast, slight green in highlights. |
| 8 | `day_for_night` | Day for Night | Skyfall night scenes | Blue shift + darker exposure. Daytime footage → night look. |
| 9 | `drone_hero` | Drone Hero | DJI showreel, Planet Earth | Landscape-punchy. Boosted sky/earth contrast, skintones preserved. |
| 10 | `cinescope` | Cinescope | Oppenheimer, Tenet | Modern Nolan clean. Slight cool cast, lifted blacks, neutral skin. |

Plus the existing `none` ("Original") pass-through preset stays — that's
not counted in the 10.

## Tuning method

For each preset:

1. **Download a free reference LUT** that matches the target look. Sources:
   FilterGrade's free pack, Color Grading Central's 100 free, RocketStock's
   35 free, PresetPro's 2026 list, IWLTBAP's free starter. Pick the one
   whose name + visual matches the target.
2. **Profile the reference LUT** by applying it to a known test image
   (16-color Macbeth chart + skin-tone patches + gray ramp + sky/earth
   gradient). Record the per-channel response curves and saturation
   shifts.
3. **Match in `GradeParams`** — dial my `exposure`, `contrast`,
   `saturation`, `temperature`, `tint`, `shadows_rgb`, `midtones_rgb`,
   `highlights_rgb`, `hue_shift`, `fade`, `vignette` until applying my
   params to the test image gets within ~5/255 levels of the reference.
4. **Verify on real footage** — run the preset on a synthetic D-Log-like
   clip and on Jasper's actual footage if available. Adjust by eye for
   the last 10%.
5. **Document the reference** in `presets.py` comments so future tuning
   has a starting point.

## Architecture changes

Minimal. The hot path stays the same:

- `core/presets.py` — replace the 20 `Preset` entries with the new 10.
  Each entry includes:
  - `id`, `name`, `description` (existing fields)
  - `params: GradeParams` (existing field, retuned)
  - **New optional field:** `reference: str` — the film reference shown in
    tooltips.
- `core/__init__.py` — no change, `PRESETS` and `get_preset` still exported.
- `ui/preset_panel.py` — tooltip now shows `description` + `reference`.
- All other code (LUT pipeline, export, UI) untouched.

## Migration

There are no saved-project files. Old preset IDs that no longer exist
silently fall back to `none` via the existing `get_preset` fallback. No
shims, no compat layer.

## Testing changes

- `tests/test_color_engine.py::test_preset_count` — assertion changes from
  `>= 20` named presets to `== 10`.
- New test: `test_preset_ids_are_stable` — pins the list of preset IDs so
  accidental renames are caught.
- New test: each preset's parameters are non-trivial (at least one of
  exposure/contrast/saturation/temperature/tint/shadows_rgb/highlights_rgb
  is non-default) — guards against shipping a preset that does nothing.
- Existing LUT/export/video-io tests are unaffected; preset choice doesn't
  matter to them.
- The verify-on-real-footage step in §"Tuning method" is manual, not
  automated, because we don't have a stable cinematic-reference frame to
  diff against.

## Open questions

None blocking. Direction-tilt was offered but Jasper signed off on the
balanced lineup, so I'm proceeding as listed.

## Risks

- **Subjective tuning.** "Looks good on a Macbeth chart" doesn't always
  mean "looks good on a vlog." Mitigation: spot-check on a synthetic
  log-ish clip after each preset is dialed in, and ship one commit per
  preset so any regressions are bisectable.
- **Reference LUTs may be missing from a build host.** That's fine —
  the tuning happens at design time, not build time. Once the
  `GradeParams` are committed, no external dependency remains.

## Out of scope (future work, not this PR)

- Bake each preset to a `.cube` at build time and ship as a static file
  alongside the LUT-loading UI (would be a small startup speedup; ignore
  for now)
- Per-preset adjustment "strength" slider (0–100%) — interesting but
  not necessary to get awesome cinematic looks
- Custom user presets / save current grade as preset
- Halation / grain / bloom film simulation

## References

- [The 10 Most Iconic Color Grades in Film (Filmworkz)](https://filmworkz.com/the-10-most-iconic-color-grades-in-fi/)
- [8 Iconic Film Color Grades (No Film School)](https://nofilmschool.com/iconic-film-color-grades)
- [How Denis Villeneuve Uses Color Palettes](https://pixflow.net/blog/how-denis-villeneuve-uses-color-palettes-to-elevate-storytelling-in-film/)
- [Free Cinematic LUTs Pack (FilterGrade)](https://filtergrade.com/free-cinematic-luts-video-editing/)
- [99+ LUTs Cinematic Color Grading Pack (IWLTBAP)](https://luts.iwltbap.com/)
- [100 Free LUTs from Color Grading Central](https://www.colorgradingcentral.com/free-luts/)
- [35 Free LUTs (RocketStock via Pond5)](https://blog.pond5.com/78810-35-free-luts-for-color-grading-videos/)
- [Best Free LUTs for Color Grading in 2026 (PresetPro)](https://www.presetpro.com/best-free-luts-color-grading-2026/)
- [Wong Kar-Wai Color Obsession](https://independent-photo.com/news/wong-kar-wai-color-obsession/)
- [CYAN: Movie Color Palettes (Filmmakers Academy)](https://www.filmmakersacademy.com/blog-cyan-movie-color-palettes/)
