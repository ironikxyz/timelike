package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"strings"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
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
	switch r.Outcome {
	case ledger.OutcomePerformed:
		s += fmt.Sprintf(" %s.%s resource=%s cost=%s expires=%s undo=%s", r.Capability, r.Action, r.Resource,
			grants.FormatMoney(deref(r.CostCents)), r.ExpiresAt.UTC().Format(time.RFC3339), r.Undo)
	case ledger.OutcomeRefused:
		s += fmt.Sprintf(" %s.%s resource=%s limit=%s allowed=%q needed=%q", r.Capability, r.Action, r.Resource,
			r.LimitName, r.Allowed, r.Needed)
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
	return map[string]any{
		"id": r.ID, "at": r.At.UTC().Format(time.RFC3339), "outcome": r.Outcome, "grant": r.Grant,
		"session": r.Session, "capability": r.Capability, "action": r.Action, "resource": r.Resource,
		"cost_cents": cost, "expires_at": expires, "undo": undo,
		"limit_name": r.LimitName, "allowed": r.Allowed, "needed": r.Needed,
	}
}
