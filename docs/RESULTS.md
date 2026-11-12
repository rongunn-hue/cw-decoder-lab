# Test results summary and caveats

Nov 2026 run, `suite.py run --tier all`, 684 cases (76 simulated operators x 9 radio conditions, 27,774 reference characters
after dropping each case's first word). Raw data: `results/tiers_all_original.json`, `results/tiers_all_rev1.json`.
"original" = OpenX6X00 decoder unchanged; "rev 1" = `decoder/` (see `VERSIONS.md`). Both receive identical audio.
Metric: character error rate (CER) = Levenshtein distance / reference length, first word of reference and output dropped
(lock acquisition). Values above 100 % mean more wrong characters than the text contained (insertions).

## By tier (all 9 conditions)
| Tier | Operators / cases | Original | Rev 1 |
|---|---|---|---|
| nominal (15-25 wpm) | 30 / 270 | 48.9 % | 30.8 % |
| slow (8-12 wpm) | 18 / 162 | 120.8 % | 67.8 % |
| fast (30-40 wpm; bug, paddle) | 10 / 90 | 33.5 % | 25.4 % |
| legacy (10, 18, 28 wpm) | 18 / 162 | 72.6 % | 41.8 % |
| all | 76 / 684 | 69.3 % | 41.4 % |

## By radio condition (CER %, original / rev 1)
| Condition | nominal | slow | fast | legacy |
|---|---|---|---|---|
| clean | 32 / 19 | 58 / 35 | 25 / 12 | 39 / 23 |
| 15 dB SNR | 30 / 18 | 58 / 35 | 25 / 13 | 39 / 23 |
| 6 dB SNR | 30 / 18 | 58 / 36 | 24 / 12 | 42 / 24 |
| 0 dB SNR | 31 / 17 | 79 / 39 | 21 / 15 | 48 / 26 |
| slow deep fading (0.5 Hz Rayleigh) | 44 / 30 | 86 / 47 | 29 / 24 | 55 / 35 |
| **fast fading (3 Hz Rayleigh)** | 117 / 78 | 262 / 122 | 83 / **90** | 159 / 88 |
| **adjacent station, 120 Hz away** | 59 / 45 | 188 / **163** | 37 / 22 | 104 / 88 |
| static crashes | 43 / 27 | 149 / 72 | 26 / 21 | 74 / 31 |
| band-pass + AGC | 54 / 28 | 149 / 63 | 31 / 18 | 93 / 39 |

## By key type (CER %, original / rev 1)
| Tier | straight | bug | paddle |
|---|---|---|---|
| nominal | 64 / 37 | 54 / 35 | 27 / 20 |
| slow | 134 / 66 | 124 / 72 | 104 / 66 |
| fast | n/a | 35 / 22 | 32 / 28 |
| legacy | 87 / 55 | 71 / 38 | 59 / 32 |

## Real-audio check
A real machine-sent recording (ARRL W1AW code practice, 20 wpm, clean) decoded by the lab scorer at 2.0 % CER for both original
and rev 1 (no regression). A later direct comparison of the shipped `cwdecode` output against ARRL's transcript found only a
trailing end-of-file marker in the transcript as a difference. I did not reconcile the two scorings, so treat the exact 2.0 %
figure as approximate. This file is machine-sent with perfect timing; it says nothing about hand-sent accuracy.

## Caveats (all apply to every number above)
1. **Simulated, not measured on real operators.** The operator model (`lab/handsim.py`) is anchored to published studies where
   numbers were available (Bell 1977 straight-key dot/dash error ~1.35 % vs the generator's 1.24 %; Koch slow-speed lengthening;
   Weber speed effect) and otherwise assumed. Assumed parameters are tagged `[ASSUMED]` in the code. Element/character-space
   variability in particular is probably somewhat too large, which inflates all error rates. **Use the numbers to compare
   decoders and conditions, not to predict real-world accuracy.**
2. **No real hand-sent recording with known text was found or tested.** This is the main missing validation.
3. **Radio effects are simple models** (white noise, Rayleigh/sinusoidal fading, one interferer type, synthetic crashes, an
   AGC, a band-pass). Real band conditions are richer.
4. **Sample size is modest** (2 seeds per key/speed/condition). Individual cells (e.g. 5-10 points) are within noise; only large
   differences are meaningful. No confidence intervals were computed.
5. **Tier ranges are my judgement** of typical speeds (15-25 wpm conversation), from general amateur-radio knowledge, not a
   measured population. Straight key above 25 wpm is excluded as unrealistic (assumed).
6. **Developed and evaluated on the same suite.** Decoder parameters (language-model weight, word-gap trigger, beam width)
   were tuned while watching this suite's results, so rev 1's numbers are optimistic relative to unseen data. Only the real
   W1AW check is independent of the generator.
7. **Scoring:** CER drops the first word, so lock-acquisition errors are excluded; with it included, errors are higher.
   Word-space errors count as characters (the no-space variant is lower: all cases 64.6 % original, 35.9 % rev 1).

## Known failures (not fixed)
- Fast fading: ~90 % CER for rev 1; in the fast-speed tier rev 1 is slightly **worse** than the original (90 vs 83 %).
- Strong adjacent station 120 Hz away: 45-88 % CER, and 163 % in the slow tier.
- Slow speeds (8-12 wpm): 68 % CER overall; below about 10 wpm unverified. In the nominal tier 15 wpm is worse than 22-25 wpm.
- One tone tracked at a time; no squelch; output arrives up to a word late; first word after start or retune is unreliable;
  the language prior is English-letter biased (callsign/number-heavy traffic gains less).
- Rev 1 has not been run on a radio or integrated into firmware.
