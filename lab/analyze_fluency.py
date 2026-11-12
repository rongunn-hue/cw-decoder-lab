#!/usr/bin/env python3
"""analyze_fluency.py - does a sender's timing roughness depend on how common the character is?
  python3 analyze_fluency.py RECORDING KNOWN_TEXT.txt [--decoder ../decoder/cwdecode] [--min-n 8] [--csv per_char.csv]
RECORDING: any audio sox can read (or a 4 kHz mono f32 raw file named *.f32). KNOWN_TEXT: what was actually sent (A-Z 0-9 and
the Morse punctuation in handsim.MORSE; spaces = word gaps).
Method: (1) run the recording through the real receiver front end (the decoder with CW_TRACE=1) to get every closed mark and gap
duration; (2) align the observed marks to the marks the known text should produce (banded dynamic programming; the first
second or so of a recording is lost to the receiver's mute and is skipped); (3) for each aligned mark take log(duration / local
centre of its class dit or dah), the local centre being a running median over neighbouring aligned marks of the same class (removes
speed drift); (4) normalise each deviation by the recording's own scale for that class (robust MAD) so dits, dahs, bug and paddle
are comparable; (5) per character: pooled roughness = RMS of normalised deviations, plus the spread of its dah/dit duration ratio;
(6) Spearman correlation between log English frequency and roughness, with a permutation p-value.
Reading it: a NEGATIVE correlation (common characters smoother) supports the hypothesis. Needs a few hundred characters; rare
characters need >= --min-n occurrences to be included. It measures timing as seen through the receiver front end (+-1-2 ms).
Validated on simulated recordings with the effect off (correlation ~0) and on; see docs/ for the result."""
import argparse, csv, math, os, subprocess, sys, wave
import numpy as np
import handsim as H

def load_f32(path):
    if path.endswith('.f32'): return np.fromfile(path, dtype='<f4')
    try:
        w = wave.open(path, 'rb')
        if w.getframerate() == 4000 and w.getnchannels() == 1 and w.getsampwidth() == 2:
            return np.frombuffer(w.readframes(w.getnframes()), '<i2').astype('<f4') / 30000.0
    except Exception: pass
    p = subprocess.run(['sox', path, '-t', 'f32', '-r', '4000', '-c', '1', '-'], capture_output=True)
    if p.returncode: sys.exit('could not read %s (sox: %s)' % (path, p.stderr.decode()[:200]))
    return np.frombuffer(p.stdout, '<f4')

def intervals(audio, decoder):
    env = dict(os.environ, CW_TRACE='1')
    p = subprocess.run(decoder, input=audio.astype('<f4').tobytes(), capture_output=True, env=env, timeout=600)
    out = []
    for line in p.stderr.decode(errors='replace').splitlines():
        if line.startswith('IV '):
            _, k, ms = line.split(); out.append((k == 'M', float(ms)))
    return out

def expected_marks(text):
    """[(char, elem_index, '.'/'-')] for every mark the text should produce."""
    E = []
    for ch in text.upper():
        if ch in H.MORSE:
            for i, e in enumerate(H.MORSE[ch]): E.append((ch, i, e))
    return E

def two_means(x, it=30):
    x = np.sort(np.asarray(x)); c0, c1 = x[len(x) // 5], x[-len(x) // 5]
    for _ in range(it):
        m = np.abs(x - c0) < np.abs(x - c1); c0n, c1n = x[m].mean(), x[~m].mean()
        if abs(c0n - c0) + abs(c1n - c1) < 1e-6: break
        c0, c1 = c0n, c1n
    return c0, c1

def align(obs, exp, skip_obs=1.5, miss_exp=1.5):
    """DP alignment of observed marks to expected marks; free expected prefix/suffix (receiver mute), observed blips cost
    skip_obs, missed elements cost miss_exp, match cost = |log(duration / class centre)|. Row-vectorised with a cumulative-min
    for the 'missed element' move."""
    c0, c1 = two_means(obs); n, m = len(obs), len(exp)
    cen = np.array([c0 if e[2] == '.' else c1 for e in exp]); jj = np.arange(m + 1) * miss_exp
    D = np.zeros((n + 1, m + 1)); D[0, :] = 0.0
    for i in range(1, n + 1):
        cand = np.empty(m + 1); cand[0] = D[i - 1, 0] + skip_obs
        cand[1:] = np.minimum(D[i - 1, :-1] + np.abs(np.log(obs[i - 1] / cen)), D[i - 1, 1:] + skip_obs)
        D[i] = np.minimum.accumulate(cand - jj) + jj
    j = int(np.argmin(D[n])); i = n; pairs = []
    while i > 0 and j > 0:
        mc = abs(math.log(obs[i - 1] / cen[j - 1]))
        if np.isclose(D[i, j], D[i - 1, j - 1] + mc): pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif np.isclose(D[i, j], D[i - 1, j] + skip_obs): i -= 1
        else: j -= 1
    return pairs[::-1], (c0, c1)

def spearman(x, y):
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])

def analyze(audio, text, decoder, min_n=8, perm=2000, seed=1):
    iv = intervals(audio, decoder); marks = [d for m, d in iv if m]
    exp = expected_marks(text)
    if len(marks) < 30: sys.exit('too few marks (%d) decoded from the recording' % len(marks))
    pairs, (c0, c1) = align(marks, exp)
    # local centre per class: running median of neighbouring aligned marks of the same class (+-15 marks)
    cls = {'.': [], '-': []}
    for oi, ej in pairs: cls[exp[ej][2]].append((oi, marks[oi]))
    dev = []
    for c, lst in cls.items():
        d = np.array([x for _, x in lst]); idx = [oi for oi, _ in lst]
        for k in range(len(d)):
            lo, hi = max(0, k - 15), min(len(d), k + 16)
            dev.append((idx[k], c, math.log(d[k] / np.median(d[lo:hi]))))
    byi = {oi: (c, r) for oi, c, r in dev}
    scale = {c: 1.4826 * np.median(np.abs([r for _, cc, r in dev if cc == c])) for c in '.-'}
    # per-character occurrences: gather the aligned marks belonging to each expected character occurrence
    occ = {}   # (expected char index group) -> list
    ci = 0; start = []; 
    # expected index -> occurrence id
    ids = []; occ_id = -1; last = None
    for j, (ch, e, _) in enumerate(exp):
        if e == 0: occ_id += 1
        ids.append(occ_id)
    per = {}   # char -> list of per-occurrence (rough, ratio)
    grp = {}
    for oi, ej in pairs:
        c, r = byi[oi]; grp.setdefault(ids[ej], []).append((exp[ej][0], c, r / scale[c], marks[oi]))
    for g, items in grp.items():
        ch = items[0][0]; n_exp = len(H.MORSE[ch])
        if len(items) != n_exp: continue                     # skip occurrences with a missed/extra element
        per.setdefault(ch, []).append(([x[2] for x in items], items))
    rows = []
    for ch, lst in per.items():
        allr = np.concatenate([a for a, _ in lst])
        ratios = []
        for _, items in lst:
            dits = [x[3] for x in items if x[1] == '.']; dahs = [x[3] for x in items if x[1] == '-']
            if dits and dahs: ratios.append(math.log(np.mean(dahs) / np.mean(dits)))
        rows.append(dict(char=ch, freq_pct=H.ENGLISH_FREQ.get(ch, 0.2), n_occ=len(lst), n_marks=len(allr),
                         rough=float(np.sqrt(np.mean(allr ** 2))), ratio_sd=float(np.std(ratios)) if len(ratios) >= 4 else float('nan')))
    use = [r for r in rows if r['n_occ'] >= min_n]
    if len(use) < 6: sys.exit('only %d characters have >= %d clean occurrences; need a longer recording' % (len(use), min_n))
    x = np.log([r['freq_pct'] for r in use]); y = np.array([r['rough'] for r in use])
    rho = spearman(x, y); rng = np.random.default_rng(seed)
    p = float(np.mean([abs(spearman(x, rng.permutation(y))) >= abs(rho) for _ in range(perm)]))
    yr = np.array([r['ratio_sd'] for r in use]); ok = ~np.isnan(yr)
    rho_r = spearman(x[ok], yr[ok]) if ok.sum() >= 6 else float('nan')
    return rows, use, rho, p, rho_r, dict(marks=len(marks), aligned=len(pairs), expected=len(exp), c0=c0, c1=c1)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('recording'); ap.add_argument('text')
    ap.add_argument('--decoder', default='../decoder/cwdecode'); ap.add_argument('--min-n', type=int, default=8)
    ap.add_argument('--csv', default='')
    a = ap.parse_args()
    text = ' '.join(open(a.text).read().split())
    rows, use, rho, p, rho_r, info = analyze(load_f32(a.recording), text, a.decoder.split(), a.min_n)
    print('marks observed %d, expected %d, aligned %d; dit centre %.0f ms, dah centre %.0f ms' % (info['marks'], info['expected'], info['aligned'], info['c0'], info['c1']))
    print('%-5s %7s %6s %7s %9s' % ('char', 'freq%', 'n', 'rough', 'ratio_sd'))
    for r in sorted(rows, key=lambda r: -r['freq_pct']):
        if r['n_occ'] >= a.min_n: print('%-5s %7.2f %6d %7.2f %9s' % (r['char'], r['freq_pct'], r['n_occ'], r['rough'], '%.3f' % r['ratio_sd'] if r['ratio_sd'] == r['ratio_sd'] else '-'))
    print('\nSpearman(log frequency, roughness) = %+.2f   permutation p = %.3f   (%d characters, >= %d occurrences each)' % (rho, p, len(use), a.min_n))
    print('Spearman(log frequency, dah/dit-ratio spread) = %+.2f' % rho_r)
    print('Negative = common characters sent more smoothly (supports the hypothesis). Near 0 / p large = no evidence either way.')
    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
