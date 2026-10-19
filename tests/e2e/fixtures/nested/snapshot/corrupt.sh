#!/bin/sh
# The criterion's corruption, as an agent's bad migration might leave it: a row changed, a row deleted, a row given
# to root, the settings' mode changed, and a stray row added. A restore must undo every one.
set -eu
printf 'corrupted\n' >>/data/rows/r2
rm /data/rows/r3
chown 0:0 /data/rows/r4
chmod 0600 /data/conf/settings
printf 'stray\n' >/data/rows/r9
