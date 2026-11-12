#!/usr/bin/env python3
"""Timing-stage lab: port of OpenX6X00 ElementTimer+MorseText (held-mark/carrier
logic omitted) vs. alternative classifiers, on simulated hand-sent CW.
Input to every decoder: list of (is_mark, duration_ms) as the detector would give,
quantised to the 8 ms step grid + edge jitter."""
import math, random, sys
import numpy as np

MORSE = {'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..',
 'J':'.---','K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...',
 'T':'-','U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..','1':'.----','2':'..---',
 '3':'...--','4':'....-','5':'.....','6':'-....','7':'--...','8':'---..','9':'----.','0':'-----',
 '/':'-..-.','?':'..--..',',':'--..--','.':'.-.-.-','=':'-...-'}
REV = {v: k for k, v in MORSE.items()}
STEP = 8.0

# ---------------- faithful(ish) port of ElementTimer ----------------
SLOTS = 300; SLOT_MS = STEP / 2
class Timer:
    def __init__(s):
        s.hist = np.zeros(SLOTS); s.n = 0; s.dot = 60.0; s.new_dot = -1; s.new_seen = 0
        s.gaps = []; s.retime()
    def retime(s):
        s.dah_from = 2.0 * s.dot; s.char_from = 1.7 * s.dot; s.word_from = 5.0 * s.dot
        if len(s.gaps) >= 8:
            g = sorted(s.gaps[-16:]); m = g[len(g)//2]
            s.word_from = max(s.word_from, min(5/3 * (m - s.dot), 3000))
    def learn(s, ms):
        s.hist *= 0.9
        mid = int(round(ms / SLOT_MS))
        if ms <= 0 or mid < 0 or mid >= SLOTS: return
        s.n += 1
        ks = [k for k in range(-4, 5) if 0 <= mid + k < SLOTS]
        tot = sum(5 - abs(k) for k in ks)
        for k in ks: s.hist[mid + k] += (5 - abs(k)) / tot
    def estimate(s, frac):
        h = s.hist; top = h.max()
        if top <= 0: return -1
        mp = frac * top
        def peak(i):
            l = h[i-1] if i > 0 else 0; r = h[i+1] if i+1 < SLOTS else 0
            return h[i] >= mp and h[i] > l and h[i] >= r
        first = next((i for i in range(SLOTS) if peak(i)), None)
        if first is None: return -1
        fm = first * SLOT_MS
        nxt = next((i for i in range(first+1, SLOTS) if peak(i) and i*SLOT_MS >= 1.7*fm), None)
        if nxt is None: nxt = min(int(round(2.2*fm/SLOT_MS)), SLOTS-1)
        if nxt <= first: nxt = min(first+1, SLOTS-1)
        low = min(range(first, nxt+1), key=lambda i: h[i])
        mass = h[:low+1].sum()
        if mass <= 0: return -1
        return (np.arange(low+1) * h[:low+1]).sum() / mass * SLOT_MS
    def backed(s, ms):
        st = s.estimate(0.25)
        return st >= 0 and abs(min(max(st, 24), 120) - ms) <= 0.25 * ms
    def set_dot(s, ms):
        if abs(ms - s.dot) <= 0.25 * s.dot:
            s.dot = min(max(s.dot + 0.3 * (ms - s.dot), 24), 120); s.new_dot = -1; s.new_seen = 0
        elif s.n < 8 or not s.backed(ms):
            s.new_dot = -1; s.new_seen = 0; return
        else:
            again = s.new_seen > 0 and abs(ms - s.new_dot) <= 0.25 * s.new_dot
            s.new_dot = ms; s.new_seen = s.new_seen + 1 if again else 1
            if s.new_seen >= 3:
                s.hist[:] = 0; s.n = 0; s.gaps = []; s.dot = ms; s.new_dot = -1; s.new_seen = 0
        s.retime()
    def close(s, mark, ms):
        if mark: sym = 'dit' if ms < s.dah_from else 'dah'
        elif ms < s.char_from: sym = 'eg'
        else: sym = 'cg' if ms < s.word_from else 'wg'
        if not mark and ms >= s.char_from: s.gaps.append(ms)
        s.learn(ms)
        d = s.estimate(0.08)
        if d >= 0: s.set_dot(min(max(d, 24), 120))
        return sym

def decode_current(intervals):
    """intervals: list of (is_mark, ms) starting with a mark, ending with a mark."""
    t = Timer(); out = []; code = ''
    def flush():
        nonlocal code
        if code: out.append(REV.get(code, '<?>'))
        code = ''
    for mark, ms in intervals:
        s = t.close(mark, ms)
        if s == 'dit': code += '.'
        elif s == 'dah': code += '-'
        elif s == 'cg': flush()
        elif s == 'wg': flush(); out.append(' ')
    flush()
    return ''.join(out)

# ---------------- simulator ----------------
WORDS = "CQ DE W1AW K5ZD UR RST 599 5NN NAME IS RON QTH TX RIG IC7300 ANT DIPOLE WX SUNNY TEMP 72 73 GL "\
        "TNX FER CALL AGN PSE QRZ BK HW CPY ES FB OM SK THE AND ARE YOU HERE WITH GOOD MORNING RADIO".split()

def make_text(rng, n_words=12):
    return ' '.join(rng.choice(WORDS) for _ in range(n_words))

def simulate(text, rng, wpm=18, ratio=3.0, ratio_sd=0.35, el_sd=0.18, gap_sd=0.2, drift=0.015,
             farns=1.0, cg_mean=3.0, wg_mean=7.0, swing=0.0):
    """Hand-sent timing. Returns intervals [(is_mark, ms)]. swing: dits long/gaps short mix (bug-like)."""
    u = 1200.0 / wpm; iv = []
    global LABELS; LABELS = []
    def jit(sd): return math.exp(rng.gauss(0, sd))
    for wi, w in enumerate(text.split(' ')):
        for ci, ch in enumerate(w):
            code = MORSE[ch]
            for ei, e in enumerate(code):
                u *= math.exp(rng.gauss(0, drift)); u = min(max(u, 1200/45), 1200/8)
                r = 1.0 if e == '.' else max(1.8, rng.gauss(ratio, ratio_sd))
                m = u * r * jit(el_sd)
                iv.append((True, m)); LABELS.append('dit' if e=='.' else 'dah')
                if ei < len(code) - 1:
                    iv.append((False, u * jit(gap_sd) * (1 - swing))); LABELS.append('eg')
            if ci < len(w) - 1:
                iv.append((False, max(1.2*u, rng.gauss(cg_mean * farns, 0.6) * u))); LABELS.append('cg')
        if wi < len(text.split(' ')) - 1:
            iv.append((False, max(3.0*u, rng.gauss(wg_mean * farns, 1.2) * u))); LABELS.append('wg')
    return iv

def quantise(iv, rng):
    """Detector view: 8 ms grid; marks measure long, gaps short by ~ one 'edge' offset."""
    out = []
    for mark, ms in iv:
        ms = ms + (6.0 if mark else -6.0) + rng.gauss(0, 3.0)
        out.append((mark, max(STEP, round(ms / STEP) * STEP)))
    return out

def lev(a, b):
    d = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j]+1, d[j-1]+1, p + (ca != cb))
    return d[-1]

# ---------------- candidate improvements ----------------
def two_means_1d(x, iters=20):
    x = np.asarray(x, float)
    c = np.array([np.percentile(x, 25), np.percentile(x, 85)])
    for _ in range(iters):
        a = np.abs(x[:, None] - c[None, :]).argmin(1)
        for k in (0, 1):
            if (a == k).any(): c[k] = x[a == k].mean()
    return c

def decode_local_clusters(intervals, win=24):
    """Per-element decisions from a sliding window of the last `win` marks and gaps:
    mark threshold = midpoint of 2-means on marks IF the clusters are plausibly separated
    (ratio>1.6), else fall back to 2*unit. Gap thresholds from log-domain 3-means on gaps
    anchored to the dit cluster centre. No global ratio constants except the anchor."""
    marks, gaps = [], []
    out = []; code = ''
    def flush():
        nonlocal code
        if code: out.append(REV.get(code, '<?>'))
        code = ''
    # two-pass: look at a window centred on each interval (non-causal) -> shows what lookahead buys
    n = len(intervals)
    for idx, (mark, ms) in enumerate(intervals):
        lo = max(0, idx - win//2); hi = min(n, idx + win//2 + 1)
        wm = [m for k, m in intervals[lo:hi] if k]
        wg = [m for k, m in intervals[lo:hi] if not k]
        if mark:
            if len(wm) >= 4:
                c = two_means_1d(wm)
                th = (c[0] + c[1]) / 2 if c[1] / c[0] > 1.8 else 2.0 * np.median(wm) * 0.9
                if c[1] / c[0] <= 1.8:   # all one kind: decide by absolute plausibility to the dit centre
                    th = 1.9 * c[0] if c[0] < 90 else 0
            else: th = 2.0 * 66
            code += '.' if ms < th else '-'
        else:
            dit = two_means_1d(wm)[0] if len(wm) >= 4 else 60.0
            if len(wg) >= 6:
                lg = np.log(np.asarray(wg))
                c = np.exp(np.sort(two_means_1d(lg)))   # element-gap vs longer gaps
                eg_c = c[0]
                # char threshold: geometric mid between element gap centre and char gap centre
                if c[1] / c[0] > 1.8: cth = math.sqrt(c[0] * c[1])
                else: cth = 2.0 * dit
                # word: gaps > 1.9x the char-gap centre, if enough long gaps exist
                longg = [g for g in wg if g > cth]
                if len(longg) >= 4:
                    lc = np.exp(np.sort(two_means_1d(np.log(longg))))
                    wth = math.sqrt(lc[0] * lc[1]) if lc[1] / lc[0] > 1.5 else max(5.0 * dit, 1.9 * lc[0])
                else: wth = max(5.0 * dit, 1.8 * np.median(longg) if longg else 5 * dit)
            else: cth, wth = 2.0 * dit, 5.0 * dit
            if ms < cth: pass
            elif ms < wth: flush()
            else: flush(); out.append(' ')
    flush(); return ''.join(out)

def run(label_decoders, trials=60, **kw):
    rng = random.Random(12345)
    tot = {k: [0, 0] for k in label_decoders}
    for _ in range(trials):
        text = make_text(rng)
        iv = quantise(simulate(text, rng, **kw), rng)
        for name, f in label_decoders.items():
            r = f(iv); tot[name][0] += lev(text, r); tot[name][1] += len(text)
    return {k: v[0] / v[1] * 100 for k, v in tot.items()}

if __name__ == '__main__':
    decs = {'current(port)': decode_current, 'local-cluster(2pass)': decode_local_clusters}
    scen = {
      'machine-like  (ratio3.0, sd small)': dict(ratio_sd=0.05, el_sd=0.04, gap_sd=0.05, drift=0.003, cg_mean=3, wg_mean=7),
      'good hand     (ratio3.0, sd .35/.18)': dict(),
      'sloppy hand   (ratio2.4, sd .5/.28)': dict(ratio=2.4, ratio_sd=0.5, el_sd=0.28, gap_sd=0.3),
      'bug-like swing(dit long, gaps short)': dict(ratio=3.5, ratio_sd=0.4, swing=0.3, el_sd=0.2),
      'fast 28 wpm  ': dict(wpm=28),
      'slow 10 wpm  ': dict(wpm=10),
      'tight chars (cg 2.2u, wg 5u)': dict(cg_mean=2.2, wg_mean=5.0),
      'speed drift 4%/elem': dict(drift=0.04),
      'Farnsworth x1.8': dict(farns=1.8),
    }
    print('%-40s' % 'scenario (CER %)', *['%22s' % k for k in decs])
    for name, kw in scen.items():
        r = run(decs, **kw)
        print('%-40s' % name, *['%22.1f' % r[k] for k in decs])
