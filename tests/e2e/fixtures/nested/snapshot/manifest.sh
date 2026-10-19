#!/bin/sh
# One line per entry of /data, root first, in byte order, each starting "m ": its path, type, mode, owner, size
# (regular files only, "-" otherwise), mtime to the nanosecond, link target ("-" for none) and the SHA-256 of a
# regular file's content ("-" otherwise). Two manifests are equal only when content, owners, modes, times and links
# are, which is what "restored to its snapshotted content" is read back by.
cd /data || exit 1
tab="$(printf '\t')"
find . -printf '%p\t%y\t%m\t%U:%G\t%s\t%T@\t%l\n' | LC_ALL=C sort | while IFS="$tab" read -r p t m o s ti l; do
  h=-
  if [ "$t" = f ]; then h="$(sha256sum "$p" | cut -c1-64)"; else s=-; fi
  echo "m ${p} ${t} ${m} ${o} ${s} ${ti} ${l:--} ${h}"
done
