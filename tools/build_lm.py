#!/usr/bin/env python3
"""build_lm.py - rebuild decoder/src/cw_lm.h (character bigram table) from ARRL W1AW/QST code-practice text.

  python3 tools/build_lm.py fetch  DIR      download the text files listed in tools/lm_urls.txt into DIR (t0.txt, t1.txt, ...)
  python3 tools/build_lm.py build  DIR OUT  train on DIR/t*.txt and write the header OUT (e.g. decoder/src/cw_lm.h)

Same procedure as the original table: drop lines containing '=' or 'W1AW' (announcements/headers), keep A-Z 0-9 and
collapse everything else to single spaces, count bigrams over " A-Z0-9", then
P(c|prev) = (count + 3*P_uni(c)) / (rowsum + 3) with P_uni floored at 1e-4; stored as natural-log values, 3 decimals.
The ARRL texts are not redistributed here; fetch them yourself. ARRL keeps adding/removing files, so a fresh fetch will
differ slightly from the shipped table (which was trained on 107,795 characters from 82 files).
"""
import glob, math, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
A = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

def fetch(d):
    os.makedirs(d, exist_ok=True); n = 0
    for u in open(os.path.join(HERE, 'lm_urls.txt')).read().split():
        try:
            req = urllib.request.Request('https://www.arrl.org' + u, headers={'User-Agent': 'cw-decoder-lab/1.0 (LM training fetch)'})
            open(os.path.join(d, 't%d.txt' % n), 'wb').write(urllib.request.urlopen(req, timeout=20).read()); n += 1
        except Exception as e:
            print('skip', u, e, file=sys.stderr)
        time.sleep(0.5)
    print(n, 'files in', d)

def build(d, out):
    # files are read in glob order, as the original did; order does not affect counts except at file joins
    txt = ' '.join(open(f, errors='ignore').read() for f in glob.glob(os.path.join(d, 't*.txt'))).upper()
    lines = [l for l in txt.replace('\r', '').split('\n') if '=' not in l and 'W1AW' not in l]
    text = re.sub(r'[^A-Z0-9]+', ' ', ' '.join(lines)); text = re.sub(r'\s+', ' ', text).strip()
    idx = {c: i for i, c in enumerate(A)}; N = len(A)
    cnt = [[0.0] * N for _ in range(N)]; uni = [0.0] * N; prev = ' '
    for c in text:
        cnt[idx[prev]][idx[c]] += 1; uni[idx[c]] += 1; prev = c
    tot = sum(uni); P = []
    for i in range(N):
        rs = sum(cnt[i])
        P.append([math.log((cnt[i][j] + 3 * max(uni[j] / tot, 1e-4)) / (rs + 3)) for j in range(N)])
    with open(out, 'w') as f:
        f.write('/* character bigram log-probs, trained on %d chars of W1AW/QST text (cwlab). index: space,A-Z,0-9 */\n#pragma once\n'
                'namespace cw {\nstatic const char LM_ALPHA[] = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";\n'
                'static const float LM_BI[%d][%d] = {\n' % (len(text), N, N))
        for r in P: f.write('{' + ','.join('%.3f' % x for x in r) + '},\n')
        f.write('};\n}\n')
    print(len(text), 'training chars ->', out)

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'fetch': fetch(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == 'build': build(sys.argv[2], sys.argv[3])
    else: print(__doc__); sys.exit(1)
