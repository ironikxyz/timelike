#!/bin/sh
# fill.sh WHAT — what a failure cell adds to /data, through `adele env exec` (014 plan R33). Kept small: the host is
# disk-bound (cross-stack P006).
#   big      100 KiB of random bytes: past nested-snapcap's 64 KiB cap
#   tiny     400 one-byte files: 400 bytes, under nested-snapfull's 1 MiB cap, yet 400 pages of a tmpfs store,
#            past its 1 MiB (256 pages of 4 KiB) — the copy meets ENOSPC in memory
#   many     30000 empty files: no data blocks, only inodes, so a copy into a tmpfs store takes long enough for the
#            runner to find and kill its helper while the copy runs
#   unready  the marker that fails the healthcheck
#   ready    the marker removed
set -eu
case "$1" in
  big) head -c 102400 /dev/urandom >/data/big ;;
  tiny)
    mkdir -p /data/tiny
    i=1
    while [ "$i" -le 400 ]; do
      printf x >"/data/tiny/f${i}"
      i=$((i + 1))
    done
    ;;
  many)
    mkdir -p /data/many
    cd /data/many
    seq 1 30000 | xargs touch
    ;;
  unready) : >/data/unready ;;
  ready) rm -f /data/unready ;;
  *) echo "fill.sh: unknown ${1}" >&2; exit 2 ;;
esac
echo "filled=${1}"
