#!/bin/bash
# usage: cwdecode.sh [-t DB] file.(wav|mp3|flac|...)   or   cwdecode.sh [-t DB] -     (raw audio on stdin: use sox args yourself)
#        live:  rec -q -t f32 -r 4000 -c 1 - | ./cwdecode 5
# -t DB : decode threshold over noise in dB (default 5; raise to 8-10 on noisy bands)
DB=5; [ "$1" = "-t" ] && DB=$2 && shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$1" ] || { echo "cwdecode.sh: no such file: $1" >&2; exit 1; }
sox "$1" -t f32 -r 4000 -c 1 - 2>/dev/null | "$HERE/cwdecode" "$DB"
