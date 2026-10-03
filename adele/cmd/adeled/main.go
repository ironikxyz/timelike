// Command adeled is Adele (feature 004, slice 0): the one authority, outside the agent's privilege,
// that holds credentials and enforces the operator's grants (P4). It serves the request interface and
// carries the operator's commands, run inside her container:
//
//	docker exec timelike-adele adeled extend <grant> <limit> <value>
//	docker exec timelike-adele adeled ledger [--json]
//
// Design: .specswarm/features/004-adele-grants/ (spec D-1..D-9; contracts/adele-http.md).
package main

import (
	"fmt"
	"io"
	"os"
)

// revision is stamped at build time with -ldflags "-X main.revision=<GIT_SHA>" (constitution H8).
var revision = ""

// Exit codes: 0 ok, 1 failure, 2 usage or a malformed grant file, 3 no such grant.
const (
	exitOK       = 0
	exitFailure  = 1
	exitUsage    = 2
	exitNotFound = 3
)

const usage = `adeled — Adele, the authority for reaching actions (run inside her container)
usage:
  adeled serve                         serve the request interface (the container's entrypoint)
  adeled check [--grants FILE]         parse the grant file; print ok or the line at fault
  adeled extend GRANT LIMIT VALUE      extend a grant (budget/ttl/instances: set; ports/capabilities: add)
  adeled ledger [--json]               print every ledger row
  adeled version                       print the build revision
  adeled health                        exit 0 if this container's Adele answers healthy (the healthcheck)
environment: ADELE_GRANTS, ADELE_DB, ADELE_CANARY_FILE, ADELE_LISTEN, ADELE_STANDIN_URL, ADELE_CONTAINER`

// env is the process environment with the container's defaults (compose.yaml; research R3).
type env func(string) string

func (e env) get(key string) string {
	if v := e(key); v != "" {
		return v
	}
	return map[string]string{
		"ADELE_GRANTS":      "/etc/adele/grants.conf",
		"ADELE_DB":          "/var/lib/adele/adele.db",
		"ADELE_CANARY_FILE": "/run/adele-secret/canary",
		"ADELE_LISTEN":      ":8480",
		"ADELE_STANDIN_URL": "http://adele-standin:8481",
		"ADELE_CONTAINER":   "timelike-adele",
	}[key]
}

func main() {
	os.Exit(run(os.Args[1:], os.Getenv, os.Stdout, os.Stderr))
}

func run(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	e := env(getenv)
	if len(args) == 0 {
		fmt.Fprintln(stderr, usage)
		return exitUsage
	}
	switch args[0] {
	case "serve":
		return serve(e, stderr, nil)
	case "check":
		return check(e, args[1:], stdout, stderr)
	case "extend":
		return extend(e, args[1:], stdout, stderr)
	case "ledger":
		return printLedger(e, args[1:], stdout, stderr)
	case "version":
		if revision == "" {
			fmt.Fprintln(stderr, "adeled: this build carries no revision stamp — rebuild with make build (H8)")
			return exitFailure
		}
		fmt.Fprintln(stdout, revision)
		return exitOK
	case "health":
		return health(e, stdout, stderr)
	case "-h", "--help", "help":
		fmt.Fprintln(stdout, usage)
		return exitOK
	}
	fmt.Fprintf(stderr, "adeled: unknown command %q\n%s\n", args[0], usage)
	return exitUsage
}
