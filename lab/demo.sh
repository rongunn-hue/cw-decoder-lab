#!/bin/bash
# demo.sh - end-to-end test: simulated hand-sent CW -> simulated radio channel -> decoder -> compare with what was sent.
#   ./demo.sh [--key straight|bug|paddle] [--wpm N] [--seed N] [--cond NAME] [--words N] [--out DIR]
#   ./demo.sh --list            list radio conditions
# Defaults: paddle key, 18 wpm, seed 1, condition snr6, 10 words, output in ./demo_out
# Needs: python3 + numpy, a built ../decoder/cwdecode (built automatically if liquid-dsp is found; LIQUID=<prefix> if not in /usr).
set -e
cd "$(dirname "$0")"
KEY=paddle; WPM=18; SEED=1; COND=snr6; WORDS=10; OUT=demo_out
while [ $# -gt 0 ]; do case $1 in
  --key) KEY=$2; shift 2;; --wpm) WPM=$2; shift 2;; --seed) SEED=$2; shift 2;; --cond) COND=$2; shift 2;;
  --words) WORDS=$2; shift 2;; --out) OUT=$2; shift 2;;
  --list) python3 apply_radio.py --list; exit 0;;
  *) sed -n '2,7p' "$0"; exit 1;; esac; done
python3 -c "import numpy" 2>/dev/null || { echo "demo.sh: python3 numpy is required (pip install numpy / apt install python3-numpy)" >&2; exit 1; }
if [ ! -x ../decoder/cwdecode ]; then echo "building decoder..."; (cd ../decoder && ./build.sh) || { echo "demo.sh: decoder build failed - install liquid-dsp (libliquid-dev) or set LIQUID=<prefix>" >&2; exit 1; }; fi
mkdir -p "$OUT"
echo "1. simulated operator: $KEY key, $WPM wpm, $WORDS words, seed $SEED"
python3 make_sample.py "$OUT/sample" --key "$KEY" --wpm "$WPM" --seed "$SEED" --words "$WORDS" --snr 200 >/dev/null
echo "2. radio channel: $COND"
python3 apply_radio.py "$OUT/sample.wav" "$OUT/sample_radio.wav" --cond "$COND" --seed "$SEED" >/dev/null
echo "3. decoding $OUT/sample_radio.wav"
python3 - "$OUT/sample_radio.wav" <<'PY' | ../decoder/cwdecode 5 > "$OUT/decoded.txt"
import sys, wave, numpy as np
w = wave.open(sys.argv[1], 'rb'); x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype('<f4') / 30000.0
sys.stdout.buffer.write(x.tobytes())
PY
echo "4. result"
python3 compare.py "$OUT/sample.txt" "$OUT/decoded.txt"
echo "files: $OUT/sample.wav (before radio)  $OUT/sample_radio.wav (after radio)  $OUT/sample.txt  $OUT/decoded.txt"
