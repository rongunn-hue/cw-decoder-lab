import math, numpy as np, timing_lab as T
FREQ = dict(zip("ETAOINSHRDLCUMWFGYPBVKJXQZ", [12.7,9.1,8.2,7.5,7.0,6.7,6.3,6.1,6.0,4.3,4.0,2.8,2.8,2.4,2.4,2.2,2.0,2.0,1.9,1.5,1.0,.8,.15,.15,.1,.07]))
LP = {c: math.log(f/100) for c, f in FREQ.items()}
for c in "0123456789": LP[c] = math.log(0.01)
for c in "/?,.=": LP[c] = math.log(0.002)
INVALID = -9.0

def params(iv, idx, win=14):
    n=len(iv); lo=max(0,idx-win); hi=min(n,idx+win+1)
    wm=[m for k,m in iv[lo:hi] if k]; wg=[m for k,m in iv[lo:hi] if not k]
    if len(wm)>=4:
        c=T.two_means_1d(wm); dit,dah=c[0],c[1]
        if dah/dit<1.7: dit,dah=min(np.median(wm),66.),3*min(np.median(wm),66.)
    else: dit,dah=66.,198.
    egc=dit
    if len(wg)>=6:
        cs=np.exp(np.sort(T.two_means_1d(np.log(wg)))); egc=min(max(cs[0],0.6*dit),1.4*dit)
    cg=3.0*dit; wgc=7.0*dit
    longg=[g for g in wg if g>2.0*dit]
    if len(longg)>=5:
        cs=np.exp(np.sort(T.two_means_1d(np.log(longg))))
        if cs[1]/cs[0]>1.6: cg,wgc=cs[0],cs[1]
        else: cg=min(np.median(longg),3.5*dit) if np.median(longg)<5*dit else 3*dit; wgc=max(np.median(longg),5.5*dit) if np.median(longg)>=5*dit else 7*dit
    return dit,dah,egc,cg,wgc

def ll(x, c, sd): return -0.5*((math.log(x)-math.log(c))/sd)**2

def decode_viterbi(iv, beam=300, sdm=0.28, sdg=0.32, lm_weight=1.0, win=14):
    states={'':(0.0,'')}
    for idx,(mark,ms) in enumerate(iv):
        dit,dah,egc,cg,wgc=params(iv,idx,win); new={}
        def put(code,score,txt):
            if code not in new or new[code][0]<score: new[code]=(score,txt)
        for code,(sc,txt) in states.items():
            if mark:
                if len(code)<7:
                    put(code+'.', sc+ll(ms,dit,sdm), txt); put(code+'-', sc+ll(ms,dah,sdm), txt)
            else:
                # element gap (continue), char gap (flush), word gap (flush+space)
                put(code, sc+ll(ms,egc,sdg)+math.log(0.55), txt) if code else None
                ch=T.REV.get(code); lp=(LM(ch) if ch else INVALID)*lm_weight if code else 0
                if code:
                    put('', sc+ll(ms,cg,sdg)+math.log(0.30)+lp, txt+(ch or '<?>'))
                    put('', sc+ll(ms,wgc,sdg)+math.log(0.15)+lp-0.0, txt+(ch or '<?>')+' ') if True else None
                else:
                    put('', sc+ll(ms,wgc,sdg)+math.log(0.15), txt+' ')
        if len(new)>beam: new=dict(sorted(new.items(), key=lambda kv:-kv[1][0])[:beam])
        states=new
    best=-1e9; out=''
    for code,(sc,txt) in states.items():
        ch=T.REV.get(code); fin=sc+((LM(ch) if ch else INVALID) if code else 0)
        if fin>best: best=fin; out=txt+((ch or '<?>') if code else '')
    return out.replace('  ',' ').strip()
def LM(ch): return LP.get(ch,-6)

if __name__=='__main__':
    decs={'current(port)':T.decode_current,'local-cluster':T.decode_local_clusters,'viterbi+params':decode_viterbi}
    scen={'good hand':{}, 'sloppy hand':dict(ratio=2.4,ratio_sd=0.5,el_sd=0.28,gap_sd=0.3),
      'bug swing':dict(ratio=3.5,ratio_sd=0.4,swing=0.3,el_sd=0.2),'fast 28':dict(wpm=28),'slow 10':dict(wpm=10),
      'tight 2.2/5':dict(cg_mean=2.2,wg_mean=5.0),'drift 4%':dict(drift=0.04),'Farnsworth 1.8':dict(farns=1.8)}
    print('%-16s'%'CER %',*['%16s'%k for k in decs])
    for n,kw in scen.items():
        r=T.run(decs,trials=25,**kw); print('%-16s'%n,*['%16.1f'%r[k] for k in decs])
