#!/usr/bin/env python3
"""suite.py - reproducible hand-sent CW test suite.

  python3 suite.py list                       show the cases (operators x radio conditions)
  python3 suite.py run --decoder ./harness    score any decoder: raw float32 mono 4000 Hz on stdin -> text on stdout
  python3 suite.py build --out DIR            write every case as WAV + JSON ground truth (for other tools / the radio)

Every case = (operator profile + text + seed) x (radio condition + seed). Ground truth (text, exact event timing,
operator profile) is regenerated bit-for-bit from the seeds, so results are comparable run to run.
Scoring: character error rate (Levenshtein / reference length) after dropping the first word of reference and hypothesis
(lock acquisition). Per-case, per-key-type, per-speed and per-condition breakdowns are printed.
"""
import argparse, json, os, re, subprocess, sys, wave, collections
import numpy as np
import handsim as H, radio as R

# Operators: key type x speed x seed.  (Persistent 'fist' sampled from handsim priors; values partly ASSUMED, see handsim.py)
OPERATORS = [dict(key=k, wpm=w, seed=1000 * (i + 1) + 10 * j + s)
             for i, k in enumerate(('straight', 'bug', 'paddle'))
             for j, w in enumerate((10, 18, 28)) for s in range(2)]

# Radio conditions (independent of the operator).
CONDITIONS = {
    'clean':      dict(snr_db=40),
    'snr15':      dict(snr_db=15),
    'snr6':       dict(snr_db=6),
    'snr0':       dict(snr_db=0),
    'qsb_deep':   dict(snr_db=15, rayleigh_hz=0.5),
    'qsb_fast':   dict(snr_db=15, rayleigh_hz=3.0),
    'qrm_adj':    dict(snr_db=20, qrm_db=-6, qrm_offset_hz=120, qrm_wpm=22),
    'qrn_crash':  dict(snr_db=20, qrn_rate=3.0, qrn_db=6),
    'agc_band':   dict(snr_db=6, band=(300, 1900), agc=True),
}

def clean_for(op, n_words=10):
    g = H.generate(op['seed'], op['key'], op['wpm'], snr_db=200.0, n_words=n_words, tone_hz=700.0)
    return g

def qrm_signal(cond, seed):
    if 'qrm_offset_hz' not in cond: return None
    g = H.generate(seed + 7777, 'straight', cond['qrm_wpm'], snr_db=200.0, n_words=40, tone_hz=700.0 + cond['qrm_offset_hz'])
    return g['audio'].astype(np.float64)

def make_case(op, cname, cache=None):
    key = op['seed']
    g = (cache or {}).get(key) or clean_for(op)
    if cache is not None: cache[key] = g
    cond = CONDITIONS[cname]
    rng = np.random.default_rng(op['seed'] * 31 + sum(map(ord, cname)))
    audio = R.apply(g['audio'], cond, rng=rng, qrm_audio=qrm_signal(cond, op['seed']))
    return g, audio

def norm(s): return re.sub(r'\s+', ' ', s).strip()
def score(ref, hyp):
    r = ref.split(' ', 1)[1] if ' ' in ref else ref
    h = hyp.split(' ', 1)[1] if ' ' in hyp else hyp
    return H.lev(r, h), len(r)

def score_ns(ref, hyp):
    r = ref.split(' ', 1)[1] if ' ' in ref else ref
    h = hyp.split(' ', 1)[1] if ' ' in hyp else hyp
    r = r.replace(' ', ''); h = h.replace(' ', '')
    return H.lev(r, h), len(r)

def run_decoder(cmd, audio):
    p = subprocess.run(cmd, input=audio.tobytes(), capture_output=True, timeout=300)
    return norm(p.stdout.decode(errors='replace'))

def cmd_list(a):
    print(len(OPERATORS), 'operators x', len(CONDITIONS), 'conditions =', len(OPERATORS) * len(CONDITIONS), 'cases')
    for o in OPERATORS: print(' ', o)
    for k, v in CONDITIONS.items(): print(' ', k, v)

def cmd_run(a):
    cmd = a.decoder.split()
    cache = {}; rows = []
    conds = a.cond.split(',') if a.cond else list(CONDITIONS)
    for op in OPERATORS:
        for cn in conds:
            g, audio = make_case(op, cn, cache)
            hyp = run_decoder(cmd, audio); e, n = score(norm(g['text']), hyp); e2, n2 = score_ns(norm(g['text']), hyp)
            rows.append(dict(key=op['key'], wpm=op['wpm'], cond=cn, e=e, n=n, e2=e2, n2=n2, seed=op['seed'], hyp=hyp, ref=norm(g['text'])))
    json.dump(rows, open(a.json, 'w'), indent=1)
    def agg(f, ns=False):
        d = collections.defaultdict(lambda: [0, 0])
        for r in rows: d[f(r)][0] += r['e2' if ns else 'e']; d[f(r)][1] += r['n2' if ns else 'n']
        return d
    tot = sum(r['e'] for r in rows), sum(r['n'] for r in rows)
    t2 = sum(r['e2'] for r in rows), sum(r['n2'] for r in rows)
    print('TOTAL CER %.1f %% (%d/%d chars, %d cases) | ignoring word spaces: %.1f %%' % (100 * tot[0] / tot[1], tot[0], tot[1], len(rows), 100 * t2[0] / t2[1]))
    for title, f in (('by condition', lambda r: r['cond']), ('by key type', lambda r: r['key']), ('by speed', lambda r: r['wpm'])):
        print(title)
        a2 = agg(f, True)
        for k, (e, n) in agg(f).items(): print('  %-10s %5.1f %%   (no-space %5.1f %%)' % (k, 100 * e / n, 100 * a2[k][0] / a2[k][1]))
    print('key x condition (CER %)')
    d = agg(lambda r: (r['key'], r['cond']))
    print('  %-9s' % '', *['%9s' % c for c in conds])
    for kt in ('straight', 'bug', 'paddle'):
        print('  %-9s' % kt, *['%9.1f' % (100 * d[(kt, c)][0] / max(1, d[(kt, c)][1])) for c in conds])

def cmd_build(a):
    os.makedirs(a.out, exist_ok=True); cache = {}; man = []
    for op in OPERATORS:
        for cn in CONDITIONS:
            g, audio = make_case(op, cn, cache); name = '%s_%dwpm_%d_%s' % (op['key'], op['wpm'], op['seed'], cn)
            w = wave.open(os.path.join(a.out, name + '.wav'), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(4000)
            w.writeframes((np.clip(audio, -1, 1) * 30000).astype('<i2').tobytes()); w.close()
            json.dump(dict(name=name, text=g['text'], op=g['op'], condition=CONDITIONS[cn], operator_seed=op['seed'],
                           lead_ms=g['t0'], events=[(e['mark'], round(e['dur'], 1), e['kind']) for e in g['events']]),
                      open(os.path.join(a.out, name + '.json'), 'w'), default=float)
            man.append(name)
    open(os.path.join(a.out, 'MANIFEST.txt'), 'w').write('\n'.join(man) + '\n'); print(len(man), 'cases written to', a.out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('list')
    r = sp.add_parser('run'); r.add_argument('--decoder', default='./harness 5'); r.add_argument('--cond', default=''); r.add_argument('--json', default='suite_results.json')
    b = sp.add_parser('build'); b.add_argument('--out', default='suite_audio')
    a = ap.parse_args(); {'list': cmd_list, 'run': cmd_run, 'build': cmd_build}[a.cmd](a)
