#!/usr/bin/env python3
"""compare.py SENT.txt DECODED.txt - print both and the character error rate (Levenshtein / reference length).
Reports CER for the whole text and with the first word dropped (the decoder's lock-acquisition word is unreliable)."""
import re, sys
import handsim as H
norm = lambda s: re.sub(r'\s+', ' ', s).strip()
ref, hyp = norm(open(sys.argv[1]).read()), norm(open(sys.argv[2]).read())
drop = lambda s: s.split(' ', 1)[1] if ' ' in s else s
print('SENT   :', ref); print('DECODED:', hyp)
e = H.lev(ref, hyp); print('character errors: %d of %d  (CER %.1f %%)' % (e, len(ref), 100 * e / max(1, len(ref))))
r2, h2 = drop(ref), drop(hyp); e2 = H.lev(r2, h2)
print('first word dropped: %d of %d  (CER %.1f %%)' % (e2, len(r2), 100 * e2 / max(1, len(r2))))
