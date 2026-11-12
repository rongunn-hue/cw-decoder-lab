# cw-decoder-lab

Analysis, a hand-sent-Morse test generator, and an improved standalone decoder, built from the CW
decoder in [Guru-RF/OpenX6X00](https://github.com/Guru-RF/OpenX6X00) (Xiegu X6100 alternative firmware;
itself derived from [gdyuldin/x6100_gui](https://github.com/gdyuldin/x6100_gui)).

| Dir | What |
|---|---|
| `decoder/` | `cwdecode`: standalone Linux decoder (stdin f32 mono 4 kHz -> text). OpenX6X00 front end unchanged; the text stage is replaced by a word-at-a-time beam search with per-operator timing estimates and a letter-pair model. Needs liquid-dsp. |
| `lab/` | `handsim.py` (human-fist generator), `radio.py` (fading/QRM/QRN/AGC), `suite.py` (162-case suite), a Python timing port, and the harnesses used for the measurements. |
| `docs/openx6x00_decoder_analysis.txt` | Full source analysis plus addenda: upstream diff, literature on hand-sent code timing, generator, decoder rev 1. |
| `tools/` | `build_lm.py`: rebuilds the decoder's bigram language-model table from ARRL W1AW/QST text. |
| `results/` | Suite results JSON: original decoder vs rev 1. |

## Quick start
```
# 1. liquid-dsp (libliquid-dev, or build https://github.com/jgaeddert/liquid-dsp and use LIQUID=<prefix>)
cd decoder && [LIQUID=<prefix>] ./build.sh            # builds ./cwdecode
./cwdecode.sh recording.wav                          # needs sox; prints text a word at a time
rec -q -t f32 -r 4000 -c 1 - | ./cwdecode 5          # live; arg = threshold dB (raise on noisy bands)

# 2. scoring (python3 + numpy)
cd ../lab && python3 suite.py list
python3 suite.py run --decoder "../decoder/cwdecode 5" --json rev1.json
# baseline: git clone https://github.com/Guru-RF/OpenX6X00 ; [LIQUID=<prefix>] ./build.sh <clone>/src/cw_decoder ./harness
python3 suite.py run --decoder "./harness 5" --json base.json

# 3. one hand-sent sample to play with (WAV + the text that was sent)
python3 make_sample.py /tmp/demo --key paddle --wpm 18 --snr 40 --seed 5
../decoder/cwdecode.sh /tmp/demo.wav; cat /tmp/demo.txt

# 4. same sample through a simulated radio channel (fading, QRM, QRN, AGC ...): python3 apply_radio.py --list
python3 make_sample.py /tmp/base --snr 200 --seed 5
python3 apply_radio.py /tmp/base.wav /tmp/base_qsb.wav --cond qsb_deep
../decoder/cwdecode.sh /tmp/base_qsb.wav; cat /tmp/base.txt
```

## Results (read the caveats)
Simulated suite character error rate: original 72.6% -> rev 1 41.8% (ignoring word spaces 67.3% -> 36.6%).
Real machine-sent W1AW 20 wpm audio: 2.0% for both (no regression).

Caveats: the suite is **simulated**. Its operator variances are partly assumptions (tagged in `handsim.py`
as `[BELL]`/`[KOCH]`/`[PDP12]`/`[WEBER]`/`[ASSUMED]`), so use it for relative comparison, not as a prediction of
real-world accuracy. No real hand-sent recordings with known text were available; contributions of such
recordings would be the most valuable addition.

Known limits: fast Rayleigh fading and a strong adjacent signal ~120 Hz away (~88% CER); speeds below ~10 wpm
unverified; one tone tracked; no squelch; output delayed up to a word; first word after lock unreliable;
language model is English-biased.

## Not included, and how to recover it
| Item | Recovery |
|---|---|
| OpenX6X00 source | `git clone https://github.com/Guru-RF/OpenX6X00`; analysed at commit `eaf1974e55ff1d775a7a8157d665e4e1a54dfc69`. Needed for `lab/harness*.cpp` baseline builds (`decoder/src` already holds the modified copy). |
| x6100_gui upstream | `git clone https://github.com/gdyuldin/x6100_gui`; compared at `a7597be6c80e80966d31b5fc8b66bbd7892a808d`. Only the upstream-diff addendum in `docs/` depends on it. |
| liquid-dsp | Built from source (1.6.0 used): https://github.com/jgaeddert/liquid-dsp ; point `decoder/build.sh` at it with `LIQUID=<install prefix>`. |
| W1AW 20 wpm audio (the real machine-sent check) | Not stored; I did not record its exact download URL. W1AW code-practice audio is published by ARRL (https://www.arrl.org/w1aw-operating-schedule lists the practice files); the transcript text for each file is on arrl.org too. Any W1AW file with its text works. |
| Language-model table | `python3 tools/build_lm.py fetch DIR` then `python3 tools/build_lm.py build DIR decoder/src/cw_lm.h`. Verified: a fresh fetch (82 files, 107,795 chars) rebuilds the shipped `cw_lm.h` byte for byte. ARRL may add or remove files, so a later fetch can differ. The ARRL texts themselves are not redistributed; `tools/lm_urls.txt` lists the 100 candidate files (18 are absolute-URL entries that the fetch skips, as the original run did). |
| Bell 1977 thesis | Naval Postgraduate School repository (NPS DSpace); I fetched it through the DSpace API. Slayton et al. 2020, PLoS ONE, PMC6944339 (Europe PMC XML). |
| Papers I could not get | Bell's JACM paper, Meisel's TSC report, Guenther 1973: access blocked or unavailable; listed in `docs/` Addendum D. |
| Suite audio | Regenerated bit-for-bit: `python3 lab/suite.py build --out DIR` (seeded). |

Not recoverable from here: exact intermediate runs (other `r_*.json` experiment files, binaries). Only the final and baseline results are in `results/`.
Nothing here modifies or builds radio firmware.

## License
LGPL-2.1-or-later, same as the code it derives from (see `LICENSE`).
