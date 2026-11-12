# lab - hand-sent CW test suite

handsim.py   human-sending model (timing layer; parameters tagged [BELL]/[KOCH]/[PDP12]/[WEBER]/[ASSUMED])
radio.py     clean audio -> received audio (noise, Rayleigh/sinusoidal fading, adjacent QRM, QRN crashes, bandpass, AGC)
suite.py     list | run --decoder CMD | build --out DIR   (18 operators x 9 conditions = 162 reproducible cases)
harness      OpenX6X00 cw::Receiver front end (stdin f32 4 kHz -> text); build with build.sh from either the OpenX6X00 clone (src/cw_decoder = baseline) or ../decoder/src (rev 1)
timing_lab.py, viterbi.py, evalsim.py   timing-stage decoders and the timing-only vs full-chain comparison
refs/        (not published: Bell 1977 thesis, Slayton 2020 - fetch from the sources cited in docs/)
CAVEAT: operator variances are only partly anchored to literature (dot/dash error 1.2% vs Bell's 1.35% for straight key);
absolute CER values are NOT measurements of real operators. Use for relative comparison and regression.
Build harness: LIQUID=<liquid-dsp prefix> ./build.sh <srcdir> ./harness   (harness2.cpp: args floor_dB [slow])
Run: python3 suite.py run --decoder "./harness 5" --json out.json   (add --cond clean,snr6 to limit; suite.py build --out DIR writes WAV+JSON)
