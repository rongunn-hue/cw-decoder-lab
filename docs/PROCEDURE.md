# Procedure: test the decoder on simulated hand-sent code

Goal: generate Morse the way a human operator might send it, degrade it the way a radio channel might, decode it,
and see how many characters came out wrong. Everything runs locally and offline.

## What is simulated (and what isn't)
1. **Operator** (`lab/handsim.py`): text sent with human-like timing for a straight key, bug or paddle: dit/dah length
   variation, uneven spacing, speed drift, slow-speed lengthening. Parameters are anchored to published studies where
   possible and otherwise assumed (tagged in the code). It is a model, not a recording of real operators.
2. **Radio channel** (`lab/radio.py`): optional noise, fading (QSB), adjacent-station interference, static crashes,
   band-pass filtering and AGC.
3. **Decoder** (`decoder/`): the real OpenX6X00 receiver front end (tone finder, tone lock, key detector) plus the
   rev-1 text stage.

## Requirements
Linux, a C++17 compiler, python3 with numpy, and [liquid-dsp](https://github.com/jgaeddert/liquid-dsp)
(`apt install libliquid-dev`, or build it and use `LIQUID=<install prefix>`). `sox` is only needed for decoding your
own recordings with `decoder/cwdecode.sh`, not for the demo.

## Steps
```
git clone https://github.com/rongunn-hue/cw-decoder-lab
cd cw-decoder-lab/decoder
[LIQUID=<prefix>] ./build.sh            # builds ./cwdecode (demo.sh does this for you if it is missing)
cd ../lab
./demo.sh                               # default: paddle key, 18 wpm, 6 dB SNR noise
```
`demo.sh` runs four stages and prints what was sent, what the decoder produced, and the character error rate (CER):

1. generates a noise-free sample (`demo_out/sample.wav`, text in `sample.txt`);
2. passes it through the chosen radio condition (`demo_out/sample_radio.wav`);
3. decodes it (`demo_out/decoded.txt`);
4. compares sent and decoded text (`compare.py`).

Example output:
```
SENT   : SUNNY WATTS 599 DE POWER 73 NAME 4589 LOW ANT
DECODED: SUCY WATTS 599 DE POWER 73 NAME E4589 LOW ANT
character errors: 3 of 45  (CER 6.7 %)
first word dropped: 1 of 39  (CER 2.6 %)
```

## Options
```
./demo.sh --key straight|bug|paddle --wpm 14 --seed 3 --cond qsb_deep --words 20 --out DIR
./demo.sh --list                        # radio conditions
```
Conditions: `clean`, `snr15`, `snr6`, `snr0` (noise levels), `qsb_deep` (slow Rayleigh fading), `qsb_fast` (fast
fading), `qrm_adj` (adjacent station 120 Hz away), `qrn_crash` (static crashes), `agc_band` (band-pass + AGC).
`--seed` changes the operator; the same options always give the same audio and result.

## Speed tiers (full suite)
The suite is split by sending speed so results at typical speeds are not blended with extremes:

| Tier | Speeds (wpm) | Keys | Operators |
|---|---|---|---|
| `nominal` | 15, 18, 20, 22, 25 | straight, bug, paddle | 30 |
| `slow` | 8, 10, 12 | all | 18 |
| `fast` | 30, 35 (bug), 30, 35, 40 (paddle) | bug, paddle only | 10 |
| `legacy` | 10, 18, 28 | all | 18 (the original set; default, kept so earlier results stay comparable) |

Each operator is run under all 9 radio conditions. Pick tiers with `--tier nominal` (comma list or `all`):
```
python3 suite.py run --decoder "../decoder/cwdecode 5" --tier nominal --json nominal.json
```
The tier ranges are my choice of "typical" (about 15-25 wpm for conversation), from general amateur-radio practice, not a
measured population. Straight key above 25 wpm is excluded as unrealistic (assumed).

### Results by tier (all 9 conditions, Nov 2026 run, simulated; `results/tiers_all_*.json`)
| Tier | Original decoder CER | Rev 1 CER |
|---|---|---|
| nominal (15-25 wpm) | 48.9 % | 30.8 % |
| slow (8-12 wpm) | 120.8 % (more insertions than characters) | 67.8 % |
| fast (30-40 wpm) | 33.5 % | 25.4 % |
| legacy (10/18/28) | 72.6 % | 41.8 % |
| all 684 cases | 69.3 % | 41.4 % |

Nominal tier excluding the two conditions that fail for any speed (`qsb_fast`, `qrm_adj`), rev 1 by key: straight 26 %,
bug 27 %, paddle 13 % (original: 51 / 43 / 17 %). Rev 1 by speed, nominal tier, all conditions: 15 wpm 38 %, 18 wpm 33 %,
20 wpm 36 %, 22 wpm 22 %, 25 wpm 25 %: slower is worse, and the slow tier is poor, so low speeds remain the weak area.
These are simulated, partly assumed operator variances; use for comparison, not as real-operator accuracy.

## Reading the result
- **The first word is unreliable** (the decoder is still locking onto the tone and speed), so CER with the first word
  dropped is the fairer figure. One sample of about 40 characters is a noisy measurement: try several seeds, or run the
  full suite (`python3 suite.py run --decoder "../decoder/cwdecode 5" --json out.json`, 162 cases).
- Expect more errors with a straight key than a paddle, and heavy errors with `qsb_fast` and `qrm_adj` (documented
  limits). Slow deep fading, noise and static are handled much better.
- Absolute CER depends on assumed operator variances; compare conditions and decoders against each other, not
  against real-operator accuracy.

## Using the pieces separately
```
python3 make_sample.py /tmp/s --key bug --wpm 22 --snr 200 --seed 4     # WAV + text (--snr 200 = no noise)
python3 apply_radio.py /tmp/s.wav /tmp/s_r.wav --cond agc_band         # radio channel
../decoder/cwdecode.sh /tmp/s_r.wav                                    # decode (needs sox)
python3 compare.py /tmp/s.txt <(../decoder/cwdecode.sh /tmp/s_r.wav)   # score
```
`decoder/cwdecode.sh` also decodes real recordings (any format sox reads), or live audio:
`rec -q -t f32 -r 4000 -c 1 - | decoder/cwdecode 5`.

## Real recordings
Simulated timing is not real sending. If you have a hand-sent recording with known text, decode it with
`cwdecode.sh`, then score it with `compare.py KNOWN.txt DECODED.txt`. Such recordings would be the best check on the
simulation, and contributions are welcome.
