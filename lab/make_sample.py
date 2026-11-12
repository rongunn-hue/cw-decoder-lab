#!/usr/bin/env python3
"""make_sample.py - write one simulated hand-sent CW recording (WAV) plus its reference text.
  python3 make_sample.py OUT_PREFIX [--key straight|bug|paddle] [--wpm 18] [--snr 40] [--seed 1] [--words 10]
Writes OUT_PREFIX.wav (4 kHz, 16-bit mono, 700 Hz tone) and OUT_PREFIX.txt (the text that was 'sent').
Then:  ../decoder/cwdecode.sh OUT_PREFIX.wav   and compare with OUT_PREFIX.txt (the first word is unreliable: lock acquisition).
Timing is simulated (see handsim.py; variances partly assumed), not a real operator.
"""
import argparse, wave, numpy as np
import handsim as H
ap = argparse.ArgumentParser(); ap.add_argument('out')
ap.add_argument('--key', default='paddle', choices=('straight', 'bug', 'paddle')); ap.add_argument('--wpm', type=float, default=18)
ap.add_argument('--snr', type=float, default=40); ap.add_argument('--seed', type=int, default=1); ap.add_argument('--words', type=int, default=10)
a = ap.parse_args()
g = H.generate(a.seed, a.key, a.wpm, snr_db=a.snr, n_words=a.words, tone_hz=700.0)
w = wave.open(a.out + '.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(4000)
w.writeframes((np.clip(g['audio'], -1, 1) * 30000).astype('<i2').tobytes()); w.close()
open(a.out + '.txt', 'w').write(' '.join(g['text'].split()) + '\n')
print('wrote', a.out + '.wav', '/', a.out + '.txt', '(%s key, %g wpm, SNR %g dB)' % (a.key, a.wpm, a.snr))
