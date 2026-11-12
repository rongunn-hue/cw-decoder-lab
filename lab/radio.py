"""radio.py - turn CLEAN keyed audio into 'received' audio. Independent of the sender model.
Input : float32 mono at fs (default 4000), made by handsim.render(..., snr_db=200) (noise-free, reference amp 0.4).
Every effect is optional and seeded. Signal reference power is the sender's on-power (0.4^2/2) so SNR means
"signal power / noise power in 2.5 kHz" exactly as in handsim.render.
"""
import math
import numpy as np

REF_PS = 0.4 ** 2 / 2

def _lowpass_noise(rng, n, fs, fc):
    """Unit-rms real Gaussian noise lowpassed at fc (FFT)."""
    x = rng.normal(0, 1, n); X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / fs); X[f > fc] = 0
    y = np.fft.irfft(X, n); return y / (y.std() + 1e-12)

def rayleigh(rng, n, fs, doppler_hz):
    """Rayleigh-like envelope (rms 1) with bandwidth ~ doppler_hz: |complex lowpass Gaussian|."""
    env = np.hypot(_lowpass_noise(rng, n, fs, doppler_hz), _lowpass_noise(rng, n, fs, doppler_hz))
    return env / math.sqrt(np.mean(env ** 2))

def impulses(rng, n, fs, rate_hz, level_db):
    """QRN crashes: exponentially decaying noise bursts. level_db relative to signal on-power (peak rms)."""
    out = np.zeros(n); amp = math.sqrt(REF_PS) * 10 ** (level_db / 20)
    for t in np.nonzero(rng.random(n) < rate_hz / fs)[0]:
        L = int(rng.uniform(0.004, 0.05) * fs); L = min(L, n - t)
        out[t:t + L] += amp * rng.normal(0, 1, L) * np.exp(-np.arange(L) / (0.3 * L))
    return out

def agc(x, fs, attack_ms=10, decay_ms=400, target=0.3):
    a = 1 - math.exp(-1000 / (attack_ms * fs)); d = 1 - math.exp(-1000 / (decay_ms * fs))
    env = 1e-3; y = np.empty_like(x)
    for i, v in enumerate(x):
        m = abs(v); env += (a if m > env else d) * (m - env); y[i] = v * target / max(env, 1e-3)
        # tracks the peak envelope: loud noise between marks pumps the gain up, as in real AGC
    return y

def bandpass(x, fs, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / fs); X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x)).astype(np.float32)

def apply(clean, cond, fs=4000, rng=None, qrm_audio=None):
    """cond keys (all optional): snr_db, rayleigh_hz, qsb_depth/qsb_hz, qrn_rate/qrn_db, qrm_db (needs qrm_audio, a clean
    signal from another operator already shifted in frequency), agc, band (lo,hi). Order: fade -> +QRM -> +QRN ->
    +noise -> bandpass -> AGC (receiver chain)."""
    rng = rng or np.random.default_rng(0)
    n = len(clean); x = clean.astype(np.float64)
    tt = np.arange(n) / fs
    if cond.get('rayleigh_hz'):
        x = x * rayleigh(rng, n, fs, cond['rayleigh_hz'])
    if cond.get('qsb_depth'):
        x = x * (1 - cond['qsb_depth'] * (0.5 + 0.5 * np.sin(2 * math.pi * cond.get('qsb_hz', 0.15) * tt + rng.uniform(0, 6.28))))
    if cond.get('qrm_db') is not None and qrm_audio is not None:
        q = qrm_audio[:n] if len(qrm_audio) >= n else np.pad(qrm_audio, (0, n - len(qrm_audio)))
        x = x + q * 10 ** (cond['qrm_db'] / 20)
    if cond.get('qrn_rate'):
        x = x + impulses(rng, n, fs, cond['qrn_rate'], cond.get('qrn_db', 0))
    if cond.get('snr_db') is not None:
        pn = REF_PS / 10 ** (cond['snr_db'] / 10)
        x = x + rng.normal(0, math.sqrt(pn * (fs / 2) / 2500.0), n)
    x = x.astype(np.float32)
    if cond.get('band'):
        x = bandpass(x, fs, *cond['band'])
    if cond.get('agc'):
        x = agc(x.astype(np.float64), fs).astype(np.float32)
    return x
