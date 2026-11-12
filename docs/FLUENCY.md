# Character-fluency hypothesis (UNVALIDATED)

> **Status: hypothesis plus simulation only. Nothing here has been tested on real human-sent code.** The effect was proposed
> by the project owner and put into the simulator by assumption. Every number on this page comes from the simulator with the
> effect built in or switched off. It shows how a decoder and an analysis script *would behave if* the effect were real. It is
> **not evidence that real operators do it**, until real recordings of known text are analysed.

## Hypothesis
Frequently used characters (E, T, A, O, I, N ...) are sent more smoothly by a typical human than rarely used ones (Q, J, X, Z, digits,
punctuation), which show more variation in dit/dah timing and dit/dah ratio. Basis: general motor-skill reasoning (automaticity from
practice). No published per-character timing study was found; the size of the effect is unknown.

## What was added
- `handsim.generate(..., fluency=h)`: `h = 0` is off (default; output is identical to before). Deviation scale inside a character is
  multiplied by `fluency_scale(ch, h)` = (2 % / English frequency)^(0.17 h), clipped 0.6-1.8, normalised so average sloppiness is
  unchanged. The exponent 0.17 and the clip are **assumed**, tagged `[HYPOTHESIS: user]`. Frequencies are a standard English letter table;
  digits and punctuation are treated as rare (0.2 %).
- `lab/fluency_experiment.py`: runs a decoder (that does not model the effect) on the same operators and texts at h = 0, 0.5, 1.0 and
  attributes errors to reference characters grouped by frequency.
- `lab/analyze_fluency.py RECORDING KNOWN_TEXT.txt`: measures per-character timing roughness in a recording of known text and reports
  the correlation with English frequency. For use on real recordings when they exist.

## Simulation results (what the effect would do to rev 1)
72 simulated transmissions (3 key types, 15-25 wpm, about 15,000 characters), rev 1 unchanged. Per-reference-character error rate:

| Characters | h = 0 (off) | h = 0.5 | h = 1.0 |
|---|---|---|---|
| frequent (>= 4 %) | 6.4 % | 6.9 % | 7.1 % |
| middle (1-4 %) | 8.3 % | 9.9 % | 11.8 % |
| rare (< 1 %, digits, punctuation) | 8.2 % | 12.3 % | 20.1 % |
| all | 7.2 % | 8.6 % | 10.7 % |
| straight key | 9.7 % | 12.2 % | 16.2 % |
| bug | 8.3 % | 10.3 % | 12.6 % |
| paddle | 3.7 % | 3.6 % | 3.6 % |

Insertions: 885, 933, 1,054. Raw data: `results/fluency_experiment.json`. These error rates exclude spaces and insertions and use
easier speeds than the suite, so they are not comparable with the suite numbers in `RESULTS.md`.

## Analysis-script validation (simulated recordings only)
Two simulated 1,831-character straight-key recordings, 18 wpm: effect off, Spearman(log frequency, roughness) = +0.12 (p = 0.50);
effect on (h = 1), -0.91 (p < 0.001). One seed and one key type. The script's second statistic (dah/dit-ratio spread) showed +0.50 with
the effect off, i.e. it is biased by character composition; do not use it.

## Caveats
1. **Circular by construction.** The simulator contains the effect only because we put it there. Detecting it in simulated data proves
   the analysis script works, not that the effect exists.
2. **Effect size and form are assumed.** Real behaviour could be weaker, stronger, per-operator, or absent. Paddle operators may show
   none.
3. **Cause not separated.** Even a real correlation could come from character length, element mix (dit-heavy vs dah-heavy) or position in
   words rather than frequency. The script normalises by dit/dah class but does not control for everything.
4. **Receiver in the loop.** Timing is measured through the receiver front end (about +-1-2 ms on clean audio).
5. **Not used by the decoder.** Rev 1 does not model fluency. The experiment shows what ignoring it would cost if it is real; a decoder
   that used it should only be built after real recordings confirm and size the effect.

## What is needed to settle it
Recordings of real hand-sent code with known text (a few hundred characters or more per operator, ideally several operators and key types).
Run `analyze_fluency.py` on each. Until then this is a hypothesis, and all simulation results here are illustrative only.
