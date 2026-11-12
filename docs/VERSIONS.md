# Decoder versions

| Name | Where | What it is |
|---|---|---|
| **upstream x6100_gui** | https://github.com/gdyuldin/x6100_gui, commit `a7597be` (2026-11-11) | The CW receiver in the original Xiegu X6100 GUI firmware project. Not modified or published here; used only for the comparison in `docs/openx6x00_decoder_analysis.txt` (Addendum A). |
| **original (OpenX6X00)** | https://github.com/Guru-RF/OpenX6X00, commit `eaf1974` (2026-11-11), `src/cw_decoder` | The decoder this project analysed. Same lineage as upstream with additions (better noise and carrier rejection). Used unmodified as the baseline: in the results it is "original". Built for the suite with `lab/harness.cpp` / `lab/harness2.cpp` against a clone of that repository. **Not in this repo.** |
| **rev 1 (`cwdecode`)** | `decoder/` in this repo | A modified copy of the original. Front end unchanged; text stage replaced. See below. In the results it is "rev 1". |

## What rev 1 changes relative to original (verified by file comparison against commit `eaf1974`)
- **Identical to the original:** `tone_finder`, `tone_lock`, `key_detector`, `element_timer.cpp`, `morse_text`, `morse_code`, `audio_resampler.h`
  (tone finding, tone lock, keying detection, speed histogram, character table).
- **New:** `soft_decoder.h/.cpp` (causal word-at-a-time likelihood/beam-search text stage with per-operator dit, dah and gap
  estimates), `cw_lm.h` (character bigram language-model table, rebuilt by `tools/build_lm.py`), `main.cpp` (stdin/stdout wrapper).
- **Small edits:** `receiver.h/.cpp` route closed mark/gap intervals to the new stage instead of the original text path (switch
  `use_soft`); `element_timer.h` adds a one-line `dot_ms()` accessor. `CMakeLists.txt` of the original is not carried over.
- **Not changed:** the radio, firmware and the original repository. Rev 1 is not integrated into any firmware and has not
  been run on a radio.

## Revision discipline
The original is never edited. Rev 1 was made as a copy. During development there were intermediate experimental builds
(soft decoder without language model, language-model weight and word-gap trigger variants); they are not published and their
numbers are not in this repo. Only the final rev 1 is. Any further change should be a new revision (rev 2, ...) beside it, with
rev 1 kept as the known reference.
