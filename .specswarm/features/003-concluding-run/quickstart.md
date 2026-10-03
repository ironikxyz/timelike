# Quickstart — `run` (feature 003, slice 0)

Inside the timelike image (any of `bash -c`, `bash -lc`, interactive):

```bash
run make test                      # verdict, then head / first errors / tail of the output
echo $?                            # make's own exit code
run --timeout 5 ./slow.sh          # stops the whole tree at 5 s, exits 124, verdict says timeout
TIMELIKE_RUN_TIMEOUT=300 run ./long-job.sh
run ./start-server.sh              # returns at once; verdict names the server's pid as detached
sed -n '51,4900p' /tmp/timelike/default/run/…log   # the "more" command from a capped verdict
run --json sh -c 'exit 42'         # {"tool":"run",…,"exit":42,"cause":"command","command_exit":42,…}
```

Verification lanes: host — `make test-host`, unit tests, lint; image — `make test` (operator / mentor,
on the host), which runs the e2e criteria SC-1–SC-5 and SC-7 under `bash -c` and `bash -lc`.
