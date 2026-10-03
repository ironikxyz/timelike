# Quickstart — Adele & grants (slice 0)

On a host with Docker, from the checkout:

```
make up            # creates adele/grants.conf if absent; builds; starts agent + Adele + stand-in (the canary is generated in Docker)
```

The example grant (`adele/grants.conf`, copied from `grants.example.conf`):

```
[grant demo]
capabilities = standin.box
budget = 1.00 USD
ttl = 1h
instances = 2
ports = 8080
```

As the agent:

```
docker exec timelike-agent bash -lc 'adele status'
docker exec timelike-agent bash -lc 'adele grants'
docker exec timelike-agent bash -lc 'adele request standin.box create --name tl-1 --ttl 1h --port 8080'
# performed: 0.25 USD, expires in 1h
docker exec timelike-agent bash -lc 'adele request standin.box create --name tl-2 --ttl 1h --port 22'
# exit 4: grant demo, limit ports (allowed 8080, needed 22), extend:
#   docker exec timelike-adele adeled extend demo ports 22
```

As the operator:

```
docker exec timelike-adele adeled extend demo ports 22
docker exec timelike-adele adeled ledger
docker exec timelike-adele-standin adele-standin list     # the stand-in's own record
```

Then the agent retries the refused request, and it proceeds. That is the D8 demo.

A malformed grant file: Adele does not start (`docker compose ps` shows her exited), and `docker logs
timelike-adele` names `grants.conf:<line>`.
