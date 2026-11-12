#!/usr/bin/env python3
"""apply_radio.py - pass a WAV through the simulated radio channel (radio.py) using a named suite condition.
  python3 apply_radio.py IN.wav OUT.wav --cond qsb_deep [--seed 1]
  python3 apply_radio.py --list
IN.wav: 4 kHz mono 16-bit (what make_sample.py writes). Make the input with --snr 200 (noise-free) so the condition's own
noise level is the only noise; the condition ADDS noise/fading/QRM/QRN/bandpass/AGC on top of whatever is in the file.
Conditions are the suite's: clean snr15 snr6 snr0 qsb_deep qsb_fast qrm_adj qrn_crash agc_band.
"""
import argparse, wave, numpy as np
import radio as R, suite as S
ap = argparse.ArgumentParser(); ap.add_argument('inp', nargs='?'); ap.add_argument('out', nargs='?')
ap.add_argument('--cond'); ap.add_argument('--seed', type=int, default=1); ap.add_argument('--list', action='store_true')
a = ap.parse_args()
if a.list or not (a.inp and a.out and a.cond):
    for k, v in S.CONDITIONS.items(): print(' ', k, v)
    raise SystemExit(0 if a.list else 1)
w = wave.open(a.inp, 'rb'); assert w.getframerate() == 4000 and w.getnchannels() == 1 and w.getsampwidth() == 2, 'need 4 kHz mono 16-bit WAV'
x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64) / 30000.0; w.close()
cond = S.CONDITIONS[a.cond]
y = R.apply(x, cond, rng=np.random.default_rng(a.seed), qrm_audio=S.qrm_signal(cond, a.seed))
o = wave.open(a.out, 'wb'); o.setnchannels(1); o.setsampwidth(2); o.setframerate(4000)
o.writeframes((np.clip(y, -1, 1) * 30000).astype('<i2').tobytes()); o.close()
print('wrote', a.out, '(condition %s: %s)' % (a.cond, cond))
