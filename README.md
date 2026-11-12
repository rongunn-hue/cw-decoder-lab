# cw-decoder-lab

Analysis, a hand-sent-Morse test generator, and an improved standalone decoder, built from the CW
decoder in [Guru-RF/OpenX6X00](https://github.com/Guru-RF/OpenX6X00) (Xiegu X6100 alternative firmware;
itself derived from [gdyuldin/x6100_gui](https://github.com/gdyuldin/x6100_gui)).

| Dir | What |
|---|---|
| `decoder/` | `cwdecode`: standalone Linux decoder (stdin f32 mono 4 kHz -> text). OpenX6X00 front end unchanged; the text stage is replaced by a word-at-a-time beam search with per-operator timing estimates and a letter-pair model. Needs liquid-dsp. |
| `lab/` | `handsim.py` (human-fist generator), `radio.py` (fading/QRM/QRN/AGC), `suite.py` (162-case suite), a Python timing port, and the harnesses used for the measurements. |
| `docs/openx6x00_decoder_analysis.txt` | Full source analysis plus addenda: upstream diff, literature on hand-sent code timing, generator, decoder rev 1. |
| `results/` | Suite results JSON: original decoder vs rev 1. |

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

## Not included
The OpenX6X00 and x6100_gui trees (clone them), liquid-dsp (build it; `decoder/build.sh` takes `$LIQUID`),
audio, and the cited papers (copyright). `lab/` scripts contain some paths from the original working tree
(`~/Chat-Projects/cwlab`); adjust as needed. Nothing here modifies or builds radio firmware.

## License
LGPL-2.1-or-later, same as the code it derives from (see `LICENSE`).
