#!/usr/bin/env python3
"""fluency_experiment.py - what does the [HYPOTHESIS: user] 'frequent characters are sent more smoothly' effect do to a decoder
that does NOT model it?  Same operators and same texts, fluency h = 0 / 0.5 / 1.0 (handsim.generate(fluency=h)), decoded by an
unchanged decoder; errors are attributed to each REFERENCE character by Levenshtein alignment and grouped by English frequency.
  python3 fluency_experiment.py [--decoder "../decoder/cwdecode 5"] [--seeds 6] [--words 60] [--snr 40] [--json out.json]
Simulated, clean-ish audio, nominal speeds 15/18/22/25 wpm, three key types. Circularity note: this measures sensitivity to the
effect, not whether real operators show it."""
import argparse, collections, json, subprocess
import numpy as np
import handsim as H

CLASS = lambda c: 'frequent' if H.ENGLISH_FREQ.get(c, 0.2) >= 4.0 else ('middle' if H.ENGLISH_FREQ.get(c, 0.2) >= 1.0 else 'rare')

def align_errors(ref, hyp):
    """Levenshtein with backtrace; returns (list of per-ref-char error flags, n_insertions)."""
    n, m = len(ref), len(hyp); D = np.zeros((n + 1, m + 1), int); D[:, 0] = range(n + 1); D[0, :] = range(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    err = [0] * n; i, j, ins = n, m, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i, j] == D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            err[i - 1] = int(ref[i - 1] != hyp[j - 1]); i -= 1; j -= 1
        elif i > 0 and D[i, j] == D[i - 1, j] + 1: err[i - 1] = 1; i -= 1
        else: ins += 1; j -= 1
    return err, ins

def run(cmd, audio):
    return ' '.join(subprocess.run(cmd, input=audio.tobytes(), capture_output=True, timeout=300).stdout.decode(errors='replace').split())

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--decoder', default='../decoder/cwdecode 5')
    ap.add_argument('--seeds', type=int, default=6); ap.add_argument('--words', type=int, default=60)
    ap.add_argument('--snr', type=float, default=40); ap.add_argument('--json', default='')
    a = ap.parse_args(); cmd = a.decoder.split()
    ops = [(k, w, 9000 + 37 * i + 5 * j + s) for i, k in enumerate(('straight', 'bug', 'paddle'))
           for j, w in enumerate((15, 18, 22, 25)) for s in range(a.seeds)]
    res = {}
    for h in (0.0, 0.5, 1.0):
        tab = collections.defaultdict(lambda: [0, 0]); ins = 0
        for k, w, seed in ops:
            g = H.generate(seed, k, w, snr_db=a.snr, n_words=a.words, fluency=h)
            ref = ' '.join(g['text'].split()); hyp = run(cmd, g['audio'])
            r2 = ref.split(' ', 1)[1]; h2 = hyp.split(' ', 1)[1] if ' ' in hyp else hyp     # drop first word (lock)
            err, i = align_errors(r2, h2); ins += i
            for c, e in zip(r2, err):
                if c == ' ': continue
                tab[CLASS(c)][0] += e; tab[CLASS(c)][1] += 1; tab['all letters+digits'][0] += e; tab['all letters+digits'][1] += 1
                tab['key:' + k][0] += e; tab['key:' + k][1] += 1
        res[h] = dict(tab=dict(tab), insertions=ins)
        print('fluency h=%.1f  (%d transmissions)' % (h, len(ops)))
    print()
    rows = ['frequent', 'middle', 'rare', 'all letters+digits', 'key:straight', 'key:bug', 'key:paddle']
    print('Decoder-ignores-the-effect: per-reference-character error rate (%), insertions not included')
    print('%-20s %12s %12s %12s   %s' % ('', 'h=0 (off)', 'h=0.5', 'h=1.0', 'n chars (h=0)'))
    for r in rows:
        v = [res[h]['tab'][r] for h in (0.0, 0.5, 1.0)]
        print('%-20s %11.1f%% %11.1f%% %11.1f%%   %d' % (r, *[100 * x[0] / x[1] for x in v], v[0][1]))
    print('insertions (extra output chars):', [res[h]['insertions'] for h in (0.0, 0.5, 1.0)])
    print('classes: frequent = English letters >= 4 % (E T A O I N S H R D L); middle 1-4 %; rare < 1 % (K J X Q Z V? see ENGLISH_FREQ) and digits/punctuation')
    if a.json: json.dump({str(h): res[h] for h in res}, open(a.json, 'w'), indent=1)
