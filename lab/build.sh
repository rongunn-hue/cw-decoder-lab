#!/bin/bash
# usage: build.sh <srcdir> <out>
L=$HOME/Chat-Projects/cwlab/local; S=$1
g++ -O2 -std=c++17 -I$L/include -I$S -o $2 harness2.cpp $S/receiver.cpp $S/tone_finder.cpp $S/tone_lock.cpp $S/key_detector.cpp $S/element_timer.cpp $S/morse_text.cpp $S/morse_code.c $( [ -f $S/soft_decoder.cpp ] && echo $S/soft_decoder.cpp ) -L$L/lib -lliquid -Wl,-rpath,$L/lib 2>&1 | grep -E 'error|Error' | head
