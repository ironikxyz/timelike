#!/bin/sh
# The failure fixture's db: one row and the .init marker on the first start, owned by root; then it waits until
# stopped, and a stop (TERM) ends it at once.
set -eu
if [ ! -e /data/.init ]; then
  printf 'row\n' >/data/f1
  : >/data/.init
fi
trap 'exit 0' TERM INT
while :; do
  sleep 1 &
  wait "$!"
done
