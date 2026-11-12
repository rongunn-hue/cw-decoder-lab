#!/bin/bash
# Build cwdecode. Needs liquid-dsp (libliquid-dev, or set LIQUID=<prefix> with include/liquid/liquid.h and lib/libliquid.*)
set -e
cd "$(dirname "$0")"
L=${LIQUID:-$HOME/Chat-Projects/cwlab/local}
INC=""; LIB=""
[ -f "$L/include/liquid/liquid.h" ] && INC="-I$L/include" && LIB="-L$L/lib -Wl,-rpath,$L/lib"
g++ -O2 -w -std=c++17 $INC -Isrc -o cwdecode src/main.cpp src/receiver.cpp src/tone_finder.cpp src/tone_lock.cpp \
    src/key_detector.cpp src/element_timer.cpp src/morse_text.cpp src/morse_code.c src/soft_decoder.cpp $LIB -lliquid
echo built ./cwdecode
