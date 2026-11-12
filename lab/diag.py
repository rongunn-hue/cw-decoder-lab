import random, collections, timing_lab as T
def diag(**kw):
    rng=random.Random(7); conf=collections.Counter(); tot=collections.Counter()
    for _ in range(80):
        text=T.make_text(rng); iv=T.quantise(T.simulate(text,rng,**kw),rng); lab=list(T.LABELS)
        t=T.Timer()
        for (m,ms),l in zip(iv,lab):
            s=t.close(m,ms); tot[l]+=1
            if s!=l: conf[(l,s)]+=1
    return conf,tot
for name,kw in [('good hand',{}),('machine',dict(ratio_sd=0.05,el_sd=0.04,gap_sd=0.05,drift=0.003))]:
    c,t=diag(**kw); print(name, dict(t))
    for (a,b),n in sorted(c.items(), key=lambda x:-x[1])[:8]: print('  true %s -> %s : %d (%.1f%% of %s)'%(a,b,n,100*n/t[a],a))
