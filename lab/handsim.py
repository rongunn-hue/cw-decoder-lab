#!/usr/bin/env python3
"""
handsim.py - statistical model of HUMAN-SENT Morse + a separate "radio" layer.

Layer 1  (timing realism)  : text -> list of mark/space events with ground truth.
Layer 2  (radio realism)   : events -> 4 kHz audio with keying edges, noise, QSB, drift.
The layers are independent so detection failures and interpretation failures can be separated.

PARAMETER PROVENANCE tags used below:
  [BELL]    structure from Bell 1977 (NPS): per-symbol instantaneous speed; Laplacian (heavy-tailed) deviation of
            normalised duration; dependence on previous symbol even for straight keys; bugs less variable on repeats.
  [KOCH]    Koch 1936 via Pierpont: below ~10 wpm dits short, dahs > 3 dits, char spaces long, intra-char space ~1 dit;
            ~10 wpm nearly standard; >=12 wpm consistent; individual peculiarities remain.
  [PDP12]   Guenther 1973: space after a dash shortens as dash lengthens; dash longer before char/word space;
            char and word space distributions overlap heavily.
  [WEBER]   Slayton 2020 (and general motor timing): SD proportional to interval; relative variability falls at
            higher speed (Weber-speed effect).
  [ASSUMED] NUMERIC VALUE IS A GUESS (no published value found). Treat as a knob, not as measured human behaviour.
Every generated transmission stores its profile + seed in a JSON sidecar.
"""
import json, math, sys, argparse, wave
import numpy as np

MORSE = {'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..',
 'J':'.---','K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...',
 'T':'-','U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..','1':'.----','2':'..---',
 '3':'...--','4':'....-','5':'.....','6':'-....','7':'--...','8':'---..','9':'----.','0':'-----',
 '/':'-..-.','?':'..--..',',':'--..--','.':'.-.-.-','=':'-...-'}
REV = {v: k for k, v in MORSE.items()}

# ---------------------------------------------------------------- operator profiles
# Per key type: [ASSUMED] values; structure [BELL]/[PDP12].
KEY_TYPES = {
    #            Laplace scale (log-domain) of: dit, dah, elem-space, char-gap, word-gap ; AR(1) rho ; dah ratio prior
    'straight': dict(b_dit=0.11, b_dah=0.11, b_es=0.20, b_cg=0.20, b_wg=0.25, rho=0.30, ratio=(3.0, 0.35), es=(1.00, 0.10)),
    'bug':      dict(b_dit=0.04, b_dah=0.12, b_es=0.17, b_cg=0.20, b_wg=0.25, rho=0.20, ratio=(3.2, 0.30), es=(0.95, 0.10)),
    'paddle':   dict(b_dit=0.03, b_dah=0.03, b_es=0.06, b_cg=0.12, b_wg=0.16, rho=0.10, ratio=(3.0, 0.05), es=(1.00, 0.03)),
}

def sample_operator(rng, key_type=None, wpm=None, sloppiness=None):
    """Draw one persistent 'fist'. All per-operator constants are sampled once and then held."""
    kt = key_type or rng.choice(['straight', 'straight', 'bug', 'paddle'])
    k = KEY_TYPES[kt]
    wpm = wpm if wpm is not None else float(rng.uniform(8, 32))
    slop = sloppiness if sloppiness is not None else float(np.exp(rng.normal(0, 0.35)))   # [ASSUMED] operator-to-operator spread
    slow = float(np.clip((12.0 - wpm) / 7.0, 0, 1))                    # [KOCH] 0 at >=12 wpm, 1 at <=5 wpm
    ratio = float(np.clip(rng.normal(*k['ratio']), 2.2, 4.4))          # operator's dah/dit ratio (not necessarily 3)
    ratio *= 1 + 0.20 * slow                                            # [KOCH] dahs > 3 dits when slow
    dit_scale = 1 - 0.15 * slow                                         # [KOCH] dits too short when slow
    es = float(np.clip(rng.normal(*k['es']), 0.7, 1.3))                 # element space in units (Koch: ~1 dit)
    cg = float(np.clip(rng.normal(3.0, 0.4), 2.0, 4.5)) * (1 + 0.5 * slow)       # [KOCH] char space long when slow
    wg = float(np.clip(rng.normal(6.8, 0.9), cg + 1.5, 10.0)) * (1 + 0.3 * slow) # word space; overlap via Laplace tails
    weber_speed = float(np.clip((15.0 / wpm) ** 0.25, 0.8, 1.4))        # [WEBER] relative variability falls as speed rises
    var_scale = slop * weber_speed * (1 + 1.0 * slow)                   # [KOCH] more irregular at low speed
    return dict(key_type=kt, wpm=wpm, sloppiness=slop, ratio=ratio, dit_scale=dit_scale, es=es, cg=cg, wg=wg,
                var_scale=var_scale, b=dict((n, k[n]) for n in ('b_dit', 'b_dah', 'b_es', 'b_cg', 'b_wg')),
                rho=k['rho'],
                speed_ar=0.92, speed_sd=0.012,        # [BELL] instantaneous speed random walk; values [ASSUMED]
                speed_step_p=0.015, speed_step_sd=0.12,   # occasional speed change per character [ASSUMED]
                hesitate_p=0.008 * slop,              # long pause inside a character [ASSUMED]
                word_as_char_p=0.03 * slop,           # word space sent like a char space [ASSUMED]
                dash_end_stretch=0.08,                # [PDP12] dash longer before char/word space (+8%) value [ASSUMED]
                space_after_dash_k=0.35)              # [PDP12] space shortens as preceding dash lengthens, k [ASSUMED]

# [HYPOTHESIS: user] character fluency: frequently used characters are sent more smoothly than rare ones.
# English letter frequencies in percent (standard table; digits/punctuation treated as rare, 0.2 %).
ENGLISH_FREQ = dict(E=12.7, T=9.1, A=8.2, O=7.5, I=7.0, N=6.7, S=6.3, H=6.1, R=6.0, D=4.3, L=4.0, C=2.8, U=2.8, M=2.4, W=2.4,
                    F=2.2, G=2.0, Y=2.0, P=1.9, B=1.5, V=1.0, K=0.8, J=0.15, X=0.15, Q=0.10, Z=0.07)
_FLU_NORM = {}
def fluency_scale(ch, h):
    """Multiplier on timing-deviation scale for the marks and element spaces INSIDE character ch. h=0: none (default).
    Raw = (2%/f)^(0.17 h), clipped 0.6-1.8 (exponent 0.17 is a [HYPOTHESIS] size, not a measurement), then divided by the
    frequency-weighted geometric mean over English letters so the AVERAGE sloppiness is unchanged: only its distribution
    across characters moves (h=1: E ~0.84x ... Q/Z ~2.0x of the operator's normal scale)."""
    raw = lambda c: float(np.clip((2.0 / ENGLISH_FREQ.get(c, 0.2)) ** (0.17 * h), 0.6, 1.8))
    if h not in _FLU_NORM:
        tot = sum(ENGLISH_FREQ.values()); _FLU_NORM[h] = math.exp(sum(f * math.log(raw(c)) for c, f in ENGLISH_FREQ.items()) / tot)
    return raw(ch) / _FLU_NORM[h]

def laplace(rng, b):
    return float(rng.laplace(0.0, b))                 # [BELL] double-sided exponential deviation

def send(text, op, rng):
    """text -> events [dict(mark, dur_ms, kind, char_index, word_index)] with ground truth."""
    base = 1200.0 / op['wpm']
    ev = []
    s = 0.0                      # log instantaneous speed offset (AR(1) around 0)  [BELL]
    dev_prev = 0.0               # AR(1) shared sloppiness chain
    last_dah_dev = 0.0
    rho = op['rho']
    words = text.split(' ')
    ci = 0
    def unit():
        nonlocal s
        s = op['speed_ar'] * s + rng.normal(0, op['speed_sd'])
        return base * math.exp(s)
    h = op.get('fluency', 0.0)
    def dev(b, m=1.0):
        nonlocal dev_prev
        d = rho * dev_prev + math.sqrt(1 - rho * rho) * laplace(rng, b * op['var_scale'] * m)
        dev_prev = d
        return d
    for wi, w in enumerate(words):
        for chi, ch in enumerate(w):
            code = MORSE[ch]; fm = fluency_scale(ch, h) if h else 1.0
            if rng.random() < op['speed_step_p']:
                s += rng.normal(0, op['speed_step_sd'])
            for ei, e in enumerate(code):
                u = unit()
                last = ei == len(code) - 1
                if e == '.':
                    d = dev(op['b']['b_dit'], fm); dur = u * op['dit_scale'] * math.exp(d); kind = 'dit'
                else:
                    d = dev(op['b']['b_dah'], fm); dur = u * op['ratio'] * math.exp(d); kind = 'dah'
                    if last: dur *= 1 + op['dash_end_stretch']
                    last_dah_dev = d
                ev.append(dict(mark=True, dur=max(dur, 15.0), kind=kind, ci=ci))
                if not last:
                    b = op['b']['b_es'] * (0.6 if e == '.' else 1.0)    # [BELL] less variable after a dot
                    d2 = dev(b, fm)
                    dur = u * op['es'] * math.exp(d2)
                    if e == '-': dur *= math.exp(-op['space_after_dash_k'] * last_dah_dev)   # [PDP12]
                    if rng.random() < op['hesitate_p']: dur += u * rng.uniform(1.0, 3.0)
                    ev.append(dict(mark=False, dur=max(dur, 15.0), kind='eg', ci=ci))
            ci += 1
            if chi < len(w) - 1:
                u = unit(); d = dev(op['b']['b_cg'])
                ev.append(dict(mark=False, dur=max(u * op['cg'] * math.exp(d), 0.9 * u), kind='cg', ci=ci - 1))
        if wi < len(words) - 1:
            u = unit(); as_char = rng.random() < op['word_as_char_p']
            d = dev(op['b']['b_wg'])
            nominal = op['cg'] if as_char else op['wg']
            ev.append(dict(mark=False, dur=max(u * nominal * math.exp(d), 1.2 * u), kind='wg', ci=ci - 1))
    return ev

# ---------------------------------------------------------------- radio layer
def render(events, fs=4000, tone_hz=700.0, snr_db=30.0, rise_ms=5.0, qsb_depth=0.0, qsb_hz=0.15,
           drift_hz=0.0, lead_s=2.0, tail_s=1.5, rng=None):
    """events -> float32 audio at fs. SNR is signal power / noise power in a 2.5 kHz bandwidth."""
    rng = rng or np.random.default_rng(0)
    tot = sum(e['dur'] for e in events) / 1000.0
    n = int((lead_s + tot + tail_s) * fs)
    key = np.zeros(n)
    t = lead_s * 1000.0
    for e in events:
        if e['mark']:
            key[int(t * fs / 1000): int((t + e['dur']) * fs / 1000)] = 1.0
        t += e['dur']
    r = max(3, int(rise_ms * fs / 1000)); win = 0.5 * (1 - np.cos(np.pi * np.arange(r) / r)); win /= win.sum()
    key = np.convolve(key, win, mode='same')                       # raised-cosine-ish shaped edges
    tt = np.arange(n) / fs
    f = tone_hz + drift_hz * np.sin(2 * np.pi * 0.03 * tt + rng.uniform(0, 6.28))
    tone = np.sin(2 * np.pi * np.cumsum(f) / fs + rng.uniform(0, 6.28))
    amp = 0.4
    if qsb_depth > 0:
        qsb = 1 - qsb_depth * (0.5 + 0.5 * np.sin(2 * np.pi * qsb_hz * tt + rng.uniform(0, 6.28)))
        key = key * qsb
    sig = amp * key * tone
    ps = amp ** 2 / 2
    pn = ps / (10 ** (snr_db / 10))                                 # noise power in 2.5 kHz
    sigma = math.sqrt(pn * (fs / 2) / 2500.0)                       # white noise over fs/2 -> scale to 2.5 kHz ref
    return (sig + rng.normal(0, sigma, n)).astype(np.float32), lead_s * 1000.0

# ---------------------------------------------------------------- helpers
WORDS = ("CQ DE UR RST 599 5NN NAME IS QTH RIG ANT DIPOLE WX SUNNY TEMP 72 73 GL TNX FER CALL AGN PSE QRZ BK HW CPY ES FB OM "
         "SK THE AND ARE YOU HERE WITH GOOD MORNING RADIO ANTENNA POWER WATTS FREQ BAND CONDX LOW HIGH NEAR FAR OPERATOR").split()
def make_text(rng, n_words=14):
    out = []
    for _ in range(n_words):
        r = rng.random()
        if r < 0.12:   # callsign-like
            out.append(rng.choice(list('KWNAV')) + str(rng.integers(0, 10)) + ''.join(rng.choice(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 2 + int(rng.integers(0, 2)))))
        elif r < 0.18:
            out.append(str(rng.integers(100, 9999)))
        else:
            out.append(str(rng.choice(WORDS)))
    return ' '.join(out)

def lev(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[-1]

def stats(ev, op):
    """Summary of the generated stream: what the 'human' actually did."""
    A = 1200.0 / op['wpm']
    g = lambda k: np.array([e['dur'] for e in ev if e['kind'] == k]) / A
    dit, dah, es, cg, wg = g('dit'), g('dah'), g('eg'), g('cg'), g('wg')
    out = dict(dit_mean=dit.mean(), dit_cv=dit.std() / dit.mean(), dah_mean=dah.mean(), dah_cv=dah.std() / dah.mean(),
               dah_dit=dah.mean() / dit.mean(), es_mean=es.mean(), es_cv=es.std() / es.mean(),
               cg_mean=cg.mean() if len(cg) else float('nan'), wg_mean=wg.mean() if len(wg) else float('nan'))
    if len(cg) and len(wg):   # overlap: fraction of word gaps shorter than the median-of-char-gap *1.7, and char gaps > 5 units
        out['wg_shorter_than_cg_p90'] = float((wg < np.percentile(cg, 90)).mean())
    return out

def generate(seed, key_type=None, wpm=None, snr_db=30.0, n_words=14, fluency=0.0, **radio):
    rng = np.random.default_rng(seed)
    op = sample_operator(rng, key_type, wpm)
    op['fluency'] = fluency     # [HYPOTHESIS: user] 0 = off (default; output identical to before)
    text = make_text(rng, n_words)
    ev = send(text, op, rng)
    audio, t0 = render(ev, snr_db=snr_db, rng=rng, **radio)
    return dict(seed=seed, text=text, op=op, events=ev, audio=audio, t0=t0, stats=stats(ev, op))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--out', default='gen')
    ap.add_argument('--key', default=None); ap.add_argument('--wpm', type=float, default=None)
    ap.add_argument('--snr', type=float, default=30.0)
    a = ap.parse_args()
    g = generate(a.seed, a.key, a.wpm, a.snr)
    g['audio'].tofile(a.out + '.f32')
    w = wave.open(a.out + '.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(4000)
    w.writeframes((np.clip(g['audio'], -1, 1) * 32000).astype('<i2').tobytes()); w.close()
    meta = dict(seed=g['seed'], text=g['text'], op=g['op'], stats=g['stats'],
                events=[(e['mark'], round(e['dur'], 1), e['kind']) for e in g['events']])
    json.dump(meta, open(a.out + '.json', 'w'), indent=1, default=float)
    print(g['text']); print(json.dumps(g['stats'], indent=1, default=float)); print(g['op']['key_type'], round(g['op']['wpm'], 1))
