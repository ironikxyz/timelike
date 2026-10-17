package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"strings"
	"time"

	"timelike/adele/internal/broker"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/reaper"
)

func check(e env, args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("check", flag.ContinueOnError)
	fs.SetOutput(stderr)
	path := fs.String("grants", e.get("ADELE_GRANTS"), "the grant file")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	file, err := grants.Load(*path)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitUsage
	}
	fmt.Fprintf(stdout, "ok: %d grants (%s)\n", len(file.Grants), strings.Join(file.Names(), ", "))
	return exitOK
}

// extend is the operator's command (spec D-4). VALUE may be several words (`2.00 USD`); they are
// joined, so the command a refusal prints works pasted as is.
func extend(e env, args []string, stdout, stderr io.Writer) int {
	if len(args) < 3 {
		fmt.Fprintln(stderr, "adeled: usage: adeled extend GRANT LIMIT VALUE — e.g. adeled extend demo budget 2.00 USD")
		return exitUsage
	}
	name, limit, value := args[0], args[1], strings.Join(args[2:], " ")
	file, err := grants.Load(e.get("ADELE_GRANTS"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitUsage
	}
	base, ok := file.Get(name)
	if !ok {
		fmt.Fprintf(stderr, "adeled: no grant named %s — the grants are: %s\n", name, strings.Join(file.Names(), ", "))
		return exitNotFound
	}
	if err := grants.ValidateExtension(limit, value); err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitUsage
	}
	led, err := ledger.Open(e.get("ADELE_DB"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: ledger %s: %v\n", e.get("ADELE_DB"), err)
		return exitFailure
	}
	defer led.Close()
	before, err := effective(led, base)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	}
	old := grants.FormatLimit(before, limit)
	if _, err := led.Extended(name, limit, old, value, time.Now().UTC()); err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	}
	after, err := effective(led, base)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	}
	fmt.Fprintf(stdout, "extended %s %s: %s → %s (recorded in the ledger)\n", name, limit, old, grants.FormatLimit(after, limit))
	return exitOK
}

func effective(led *ledger.Ledger, g grants.Grant) (grants.Grant, error) {
	exts, err := led.Extensions(g.Name)
	if err != nil {
		return g, err
	}
	conv := make([]grants.Extension, len(exts))
	for i, x := range exts {
		conv[i] = grants.Extension{Grant: x.Grant, Limit: x.Limit, Value: x.Value}
	}
	return grants.Effective(g, conv)
}

func printLedger(e env, args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("ledger", flag.ContinueOnError)
	fs.SetOutput(stderr)
	asJSON := fs.Bool("json", false, "one JSON array")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	led, err := ledger.Open(e.get("ADELE_DB"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: ledger %s: %v\n", e.get("ADELE_DB"), err)
		return exitFailure
	}
	defer led.Close()
	rows, err := led.Rows()
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	}
	if *asJSON {
		out := make([]map[string]any, 0, len(rows))
		for _, r := range rows {
			out = append(out, jsonRow(r))
		}
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(out)
		return exitOK
	}
	for _, r := range rows {
		fmt.Fprintln(stdout, rowLine(r))
	}
	fmt.Fprintf(stdout, "%d rows\n", len(rows))
	return exitOK
}

func rowLine(r ledger.Row) string {
	s := fmt.Sprintf("#%d %s %s grant=%s session=%s", r.ID, r.At.UTC().Format(time.RFC3339), r.Outcome, r.Grant, r.Session)
	if r.Agent != "" {
		s += " agent=" + r.Agent
	}
	switch r.Outcome {
	case ledger.OutcomePerformed:
		s += fmt.Sprintf(" %s.%s resource=%s cost=%s expires=%s undo=%s", r.Capability, r.Action, r.Resource,
			grants.FormatMoney(deref(r.CostCents)), r.ExpiresAt.UTC().Format(time.RFC3339), r.Undo)
	case ledger.OutcomeRefused:
		s += fmt.Sprintf(" %s.%s resource=%s limit=%s allowed=%q needed=%q", r.Capability, r.Action, r.Resource,
			r.LimitName, r.Allowed, r.Needed)
		if r.Host != "" {
			s += " host=" + r.Host
		}
	case ledger.OutcomeReaped, ledger.OutcomeGone, ledger.OutcomeReapFailed:
		s += fmt.Sprintf(" %s.%s resource=%s of=#%d attempts=%d cause=%q", r.Capability, r.Action, r.Resource,
			deref(r.Ref), derefInt(r.Attempts), r.Cause)
	default: // extended: Allowed is the value before, Needed the extension as given (data-model § Ledger)
		verb := "set to"
		if r.LimitName == grants.LimitPorts || r.LimitName == grants.LimitCapabilities {
			verb = "added"
		}
		s += fmt.Sprintf(" limit=%s was %q, %s %q", r.LimitName, r.Allowed, verb, r.Needed)
	}
	return s
}

func deref(p *int64) int64 {
	if p == nil {
		return 0
	}
	return *p
}

func derefInt(p *int) int {
	if p == nil {
		return 0
	}
	return *p
}

// jsonRow is the ledger's JSON shape for the operator and the e2e tests: the data model's column
// names, absent values as null (data-model § Ledger).
func jsonRow(r ledger.Row) map[string]any {
	var expires any
	if r.ExpiresAt != nil {
		expires = r.ExpiresAt.UTC().Format(time.RFC3339)
	}
	var cost any
	if r.CostCents != nil {
		cost = *r.CostCents
	}
	var undo any
	if r.Undo != "" {
		undo = json.RawMessage(r.Undo)
	}
	var ref, attempts any
	if r.Ref != nil {
		ref = *r.Ref
	}
	if r.Attempts != nil {
		attempts = *r.Attempts
	}
	return map[string]any{
		"id": r.ID, "at": r.At.UTC().Format(time.RFC3339), "outcome": r.Outcome, "grant": r.Grant,
		"session": r.Session, "capability": r.Capability, "action": r.Action, "resource": r.Resource,
		"cost_cents": cost, "expires_at": expires, "undo": undo,
		"limit_name": r.LimitName, "allowed": r.Allowed, "needed": r.Needed,
		// slice 1 (schema 2): absent values as null, as the slice-0 keys are (spec FR-31)
		"ref": ref, "agent": nullStr(r.Agent), "cause": nullStr(r.Cause), "attempts": attempts,
		"host": nullStr(r.Host), "extend": nullStr(r.Extend),
	}
}

func nullStr(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// reapNow is the operator's `adeled reap` (spec FR-28): one pass over every due row, given-up ones
// included and waits ignored, with this container's credential. It prints each outcome.
func reapNow(e env, args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("reap", flag.ContinueOnError)
	fs.SetOutput(stderr)
	asJSON := fs.Bool("json", false, "one JSON array")
	if err := fs.Parse(args); err != nil || fs.NArg() != 0 {
		return exitUsage
	}
	b, led, code := setup(e, stderr)
	if code != exitOK {
		return code
	}
	defer led.Close()
	r, err := newReaper(e, led, b.Upstream.(*broker.StandinClient), nil, b.Envs)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitUsage
	}
	results, err := r.Pass(context.Background(), true)
	if *asJSON {
		if results == nil {
			results = []reaper.Result{}
		}
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(results)
	} else {
		for _, res := range results {
			fmt.Fprintln(stdout, reaper.Line(res))
		}
		fmt.Fprintf(stdout, "%d reaped or recorded (%s)\n", len(results), countOutcomes(results))
	}
	if err != nil {
		fmt.Fprintf(stderr, "adeled: reap: %v\n", err)
		return exitFailure
	}
	for _, res := range results {
		if res.Outcome == ledger.OutcomeReapFailed {
			return exitFailure
		}
	}
	return exitOK
}

func countOutcomes(rs []reaper.Result) string {
	n := map[string]int{}
	for _, r := range rs {
		n[r.Outcome]++
	}
	return fmt.Sprintf("reaped %d, gone %d, failed %d", n[ledger.OutcomeReaped], n[ledger.OutcomeGone], n[ledger.OutcomeReapFailed])
}

// status is the operator's `adeled status [HOST]` (spec FR-36): this Adele's revision (P003), the
// reaper's due and given-up rows, and the recent denials — each explained, newest first. A verdict line
// comes first; --json prints one document.
func status(e env, args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("status", flag.ContinueOnError)
	fs.SetOutput(stderr)
	asJSON := fs.Bool("json", false, "one JSON document")
	if err := fs.Parse(args); err != nil || fs.NArg() > 1 {
		fmt.Fprintln(stderr, "adeled: usage: adeled status [HOST] [--json]")
		return exitUsage
	}
	host := fs.Arg(0)
	led, err := ledger.Open(e.get("ADELE_DB"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: ledger %s: %v\n", e.get("ADELE_DB"), err)
		return exitFailure
	}
	defer led.Close()
	r, err := newReaper(e, led, nil, nil, nil)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitUsage
	}
	now := time.Now().UTC()
	due, err := led.Due(now)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	}
	passes := r.Passes
	if passes == 0 {
		passes = reaper.DefaultPasses
	}
	var givenUp []map[string]any
	for _, d := range due {
		if d.Failures >= passes {
			givenUp = append(givenUp, map[string]any{"ref": d.Row.ID, "resource": d.Row.Resource,
				"grant": d.Row.Grant, "failures": d.Failures, "retry": r.OperatorCommand()})
		}
	}
	doc, err := broker.Denials(led, now, host)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	}
	rev := revision
	if rev == "" {
		rev = "unstamped"
	}
	if *asJSON {
		if givenUp == nil {
			givenUp = []map[string]any{}
		}
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(map[string]any{"revision": rev, "reaper": map[string]any{"due": len(due), "given_up": givenUp},
			"denials": doc})
		return exitOK
	}
	fmt.Fprintln(stdout, statusVerdict(rev, len(due), len(givenUp), doc))
	for _, line := range denialLines(doc) {
		fmt.Fprintln(stdout, line)
	}
	for _, g := range givenUp {
		fmt.Fprintf(stdout, "given up: #%v %v (grant %v) after %v failed passes — retry: %v\n",
			g["ref"], g["resource"], g["grant"], g["failures"], g["retry"])
	}
	return exitOK
}

func statusVerdict(rev string, due, givenUp int, doc map[string]any) string {
	n := doc["count"].(int)
	where := ""
	if h, _ := doc["host"].(string); h != "" {
		where = " of " + h
	}
	denials := fmt.Sprintf("no denial%s in the last %d h", where, doc["window_hours"])
	if n > 0 {
		denials = fmt.Sprintf("%d denial%s%s in the last %d h (newest first, at most %d per host)",
			n, plural(n), where, doc["window_hours"], doc["per_host"])
	}
	// Where the record lives (Item 26 Q2, the mentor's addition): the operator's own command reads it.
	return fmt.Sprintf("Adele revision %s · reaper: %d due, %d given up · %s · the record: adeled ledger",
		rev, due, givenUp, denials)
}

// denialLines explains each denial: when, where, the policy that denied it, and the operator's command.
func denialLines(doc map[string]any) []string {
	var out []string
	for _, d := range doc["denials"].([]map[string]any) {
		l := d["limit"].(map[string]string)
		host, _ := d["host"].(string)
		if host == "" {
			host = "(no host recorded: refused before slice 1)"
		}
		line := fmt.Sprintf("#%v %v %s: grant %v, %s allows %s, needed %s — the operator allows it: %v",
			d["ledger_id"], d["at"], host, d["grant"], l["name"], l["allowed"], l["needed"], d["extend"])
		if a, _ := d["agent"].(string); a != "" {
			line += fmt.Sprintf(" (session %v, agent %s)", d["session"], a)
		} else {
			line += fmt.Sprintf(" (session %v)", d["session"])
		}
		out = append(out, line)
	}
	return out
}

func plural(n int) string {
	if n == 1 {
		return ""
	}
	return "s"
}
