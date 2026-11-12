# Rev 1: what was actually changed

Base: OpenX6X00 commit `eaf1974`, `src/cw_decoder`. Rev 1 = a copy with the changes below. Exact source diff of the three
edited original files: `decoder/rev1-vs-original.diff`. New files are `decoder/src/soft_decoder.{h,cpp}`, `cw_lm.h`, `main.cpp`.

## Unchanged (byte-identical to the original)
Tone finder, tone lock (NCO + LPF + PLL), key detector (Schmitt trigger, edge confirmation, carrier floor),
`element_timer.cpp`, `morse_text`, `morse_code`, `audio_resampler.h`. Measured on clean simulated audio the front end
times marks and gaps to about +-1-2 ms (IQR), median bias +2..+7.5 ms on marks and the opposite on gaps, no gross mismatches.

## The one design change: the text stage
**Original:** `ElementTimer` keeps a histogram of mark lengths, estimates one dot length, and classifies each element with
fixed boundaries in dots (`element_timer.cpp`: dit/dah 2.0, element/character gap 1.7, character/word gap 5.0).
`MorseText` then looks the dots and dashes up in a table.
**Rev 1:** the hard thresholds are bypassed. Every closed mark or gap duration goes to `SoftDecoder` instead (the original
text path is switched off by `use_soft_`, default on):
1. **Per-operator timing estimates** from the last 64 intervals (`HIST_MAX`): dit and dah centres by 2-means on mark
   lengths (falling back to the median if the two clusters are not 1.7x apart; the element timer's dot length is the prior);
   element-gap, character-gap and word-gap centres by 2-means in the log domain; the operator's own spread (standard
   deviation of log residuals, clamped to 0.10-0.45) for marks and for gaps.
2. **Scoring:** each mark is scored as dit or dah, each gap as element, character or word gap, under log-normal-style
   densities at those centres (priors 0.55 / 0.30 / 0.15 for element / character / word gap).
3. **Beam search** (width 200, state = partial character + last letter) over a word's intervals; the most likely whole word
   wins. Output is emitted one word at a time.
4. **Character bigram language prior** (`cw_lm.h`, weight 0.5, trained on 107,795 characters of W1AW/QST text, rebuilt by
   `tools/build_lm.py`). Symbols not in the table (punctuation, prosigns) get a flat penalty; an unknown code is heavily
   penalised.
5. **Word end:** the word is flushed when the running gap reaches max(sqrt(charGap x wordGap), 4 dits).
6. **Noise handling:** a mark shorter than 0.3 dits is swallowed as a blip and the gaps around it merged; a mark longer than
   3 dahs is treated as a carrier and discards the pending word; a weak (non-"strong") lone mark under 2.5 dits does not open
   a word; a word that reaches 96 intervals (`PEND_MAX`) is force-decoded, only at a decided character boundary.

## Small edits to original files (see the diff)
- `receiver.h/.cpp`: construct a `SoftDecoder` that shares the text callback; accumulate run length per detector step; on
  each edge pass the closed interval to `SoftDecoder::interval()` and call `idle()` each step while the key is up; call the
  original `text_.put()` only if `use_soft_` is false. `use_soft(bool)` is the switch.
- `element_timer.h`: a one-line `dot_ms()` getter.
- `main.cpp` (new): reads float32 mono 4 kHz from stdin, runs `cw::Receiver`, prints text.

## Mistakes found and fixed during development (so you know what the final form protects against)
- Word split too early ("NEA R", "AN D"): word-flush trigger settled at 1.0 x sqrt(cg x wg) after trying 0.9 x wg and 1.25 x.
- Forced cut at 56 intervals flushed half-built characters (W1AW "SPECIFICATIONS" decoded wrongly): limit raised to 96 and
  restricted to character boundaries; real-audio error back to its earlier value.

## Tried and not adopted
Slow-speed mode of the original timer (no gain at 10 wpm); earlier word flush (splits words); language-model weights 1.0-1.5 (worse).
These were evaluated on the same simulated suite used for the results, so some tuning was done on test data
(see `docs/RESULTS.md`, caveat 6). The intermediate experimental builds are not published.

## What this does not do
No front-end change: fast fading, an adjacent station about 120 Hz away, multiple tones, and squelch are unaddressed.
Not run on a radio, not integrated into firmware.
