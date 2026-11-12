# cwdecode - standalone Linux CW decoder (rev 1; "cwlab" in source comments is the original working-directory name)

Derived from the OpenX6X00 CW receiver (LGPL-2.1-or-later; itself from gdyuldin/x6100_gui). Same front end
(FFT tone finder, PLL tone lock, Schmitt keying detector, speed histogram); the hard-threshold text stage is replaced by
a causal likelihood decoder (src/soft_decoder.*): every mark/gap is scored as dit/dah and element/char/word gap with
per-operator estimated centres and spreads, a beam search picks the most likely text one word at a time, with a
character-bigram prior (src/cw_lm.h, trained on W1AW/QST text).

Use:  ./build.sh   (needs liquid-dsp)    ./cwdecode.sh recording.wav     rec -q -t f32 -r 4000 -c 1 - | ./cwdecode 5
Output appears a word at a time (decoder waits for a word gap).

MEASURED (lab/suite.py, 162 simulated hand-sent cases; absolute numbers depend on ASSUMED operator variances):
  original OpenX6X00 decoder: CER 72.6 %   this decoder: 41.8 %   (clean machine-sent W1AW 20 wpm: 2.0 % both)
  by condition (this decoder): clean 23, 15 dB 24, 6 dB 24, 0 dB 26, slow deep fading 35, crashes 31, bandpass+AGC 39
KNOWN LIMITS (not fixed): fast fading (3 Hz Rayleigh) ~88 %, strong adjacent station 120 Hz away ~88 %, speeds below
~10 wpm unverified, one tone tracked at a time, no squelch (prints noise on empty bands - raise -t), output delayed by up
to a word, the language prior is English letters (callsign/number heavy traffic gains less), first word after
start/retune is unreliable (1 s mute + lock acquisition).
Test suite and generator: ../lab (from that directory: python3 suite.py run --decoder "../decoder/cwdecode 5").
