import subprocess, sys, re, numpy as np, collections
import handsim as H, timing_lab as T, viterbi as V
def norm(s): return re.sub(r'\s+',' ',s).strip()
def front_end(audio):
    p=subprocess.run(['./harness','5'],input=audio.tobytes(),capture_output=True)
    return norm(p.stdout.decode(errors='replace'))
def quant(ev,rng):
    out=[]
    for e in ev:
        ms=e['dur']+(6.0 if e['mark'] else -6.0)+rng.normal(0,3.0)
        out.append((e['mark'],max(8.0,round(ms/8.0)*8.0)))
    return out
def score(ref,hyp):
    r=ref.split(' ',1)[1] if ' ' in ref else ref   # drop first word (lock acquisition / preamble)
    h=hyp
    # align: drop hyp's first word as well
    h=h.split(' ',1)[1] if ' ' in h else h
    return H.lev(r,h),len(r)
N=int(sys.argv[1]) if len(sys.argv)>1 else 24
res=collections.defaultdict(lambda:[0,0]); bykey=collections.defaultdict(lambda:[0,0]); stat=[]
for seed in range(100,100+N):
    for snr in (30,12,6):
        g=H.generate(seed,snr_db=snr)
        ref=norm(g['text']); kt=g['op']['key_type']
        rng=np.random.default_rng(seed)
        if snr==30:
            iv=quant(g['events'],rng); stat.append(g['stats'])
            for name,f in (('timing: current port',T.decode_current),('timing: viterbi',V.decode_viterbi)):
                e,n=score(ref,norm(f(iv))); res[name][0]+=e; res[name][1]+=n
                bykey[(name,kt)][0]+=e; bykey[(name,kt)][1]+=n
        hyp=front_end(g['audio']); e,n=score(ref,hyp)
        res['front end @%d dB'%snr][0]+=e; res['front end @%d dB'%snr][1]+=n
        if snr==30: bykey[('front end @30 dB',kt)][0]+=e; bykey[('front end @30 dB',kt)][1]+=n
print('CER %% over %d operators/texts'%N)
for k,(e,n) in res.items(): print('  %-26s %5.1f %%  (%d/%d chars)'%(k,100*e/n,e,n))
print('by key type (30 dB):')
for (name,kt),(e,n) in sorted(bykey.items()): print('  %-22s %-9s %5.1f %%'%(name,kt,100*e/n))
import statistics as S
print('generated stream means:',{k:round(S.mean(x[k] for x in stat if x[k]==x[k]),2) for k in ('dah_dit','dit_cv','dah_cv','es_cv','cg_mean','wg_mean')})
