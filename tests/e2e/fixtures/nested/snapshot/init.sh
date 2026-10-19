#!/bin/sh
# The criterion fixture's db (014 plan R33). On its first start: 8 rows of 512 random bytes, a settings file, a
# symbolic link and the .init marker on /data, 4100 bytes in 13 entries, every one owned by uid 999. A restored
# volume keeps its .init, so a restart after a restore never writes the rows again; random rows make a rewrite
# visible. Then it waits until stopped, and a stop (TERM) ends it at once.
set -eu
if [ ! -e /data/.init ]; then
  mkdir -p /data/rows /data/conf
  for i in 1 2 3 4 5 6 7 8; do head -c 512 /dev/urandom >"/data/rows/r${i}"; done
  printf 'k=v\n' >/data/conf/settings
  ln -s rows/r1 /data/latest
  chmod 0700 /data/rows
  chmod 0640 /data/conf/settings
  chown -R 999:999 /data
  chown -h 999:999 /data/latest
  : >/data/.init
  chown 999:999 /data/.init
fi
trap 'exit 0' TERM INT
while :; do
  sleep 1 &
  wait "$!"
done
