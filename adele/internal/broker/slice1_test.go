package broker

import (
	"context"
	"errors"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestAgentIsRecordedOnPerformedAndRefusedRows(t *testing.T) {
	f := newFixture(t, demoGrant)
	req := boxReq("box-a", "", 8080)
	req.Agent = "agent-a"
	if out := f.handle(req); out.Status != 200 {
		t.Fatalf("performed: %d %v", out.Status, out.Body)
	}
	bad := boxReq("box-b", "", 22)
	bad.Agent = "agent-b"
	if out := f.handle(bad); out.Status != 403 {
		t.Fatalf("refused: %d %v", out.Status, out.Body)
	}
	anon := boxReq("box-c", "", 8080) // no TIMELIKE_AGENT: no agent recorded, as before slice 1
	if out := f.handle(anon); out.Status != 200 {
		t.Fatalf("anonymous: %d", out.Status)
	}
	rows := f.rows(t)
	if rows[0].Agent != "agent-a" || rows[1].Agent != "agent-b" || rows[2].Agent != "" {
		t.Fatalf("agents = %q %q %q", rows[0].Agent, rows[1].Agent, rows[2].Agent)
	}
}

func TestBadAgentNameIsAUsageErrorAndRecordsNothing(t *testing.T) {
	f := newFixture(t, demoGrant)
	req := boxReq("box-a", "")
	req.Agent = "bad agent!"
	out := f.handle(req)
	if out.Status != 400 || !strings.Contains(out.Body["error"].(string), "agent") {
		t.Fatalf("bad agent: %d %v", out.Status, out.Body)
	}
	if len(f.rows(t)) != 0 || len(f.store.List()) != 0 {
		t.Fatal("a bad agent name recorded or performed something")
	}
}

func TestRefusalRecordsHostAndTheOperatorsCommand(t *testing.T) {
	f := newFixture(t, demoGrant)
	out := f.handle(boxReq("box-a", "", 22))
	u, _ := url.Parse(f.srv.URL)
	if out.Status != 403 || out.Body["host"] != u.Host {
		t.Fatalf("refusal = %d %v; want host %s", out.Status, out.Body, u.Host)
	}
	r := f.rows(t)[0]
	if r.Host != u.Host || r.Extend != out.Body["extend"] || !strings.HasPrefix(r.Extend, "docker exec ") {
		t.Fatalf("row host %q extend %q (envelope %v)", r.Host, r.Extend, out.Body["extend"])
	}
}

func TestDenialsEndpointByHost(t *testing.T) {
	f := newFixture(t, demoGrant)
	srv := f.adele(t)
	u, _ := url.Parse(f.srv.URL)
	// none yet
	resp, body := call(t, "GET", srv.URL+"/v1/denials?host="+url.QueryEscape(u.Host), "")
	if resp.StatusCode != 200 || body["count"].(float64) != 0 || body["window_hours"].(float64) != 24 ||
		body["per_host"].(float64) != 20 || body["revision"] != "rev-test" {
		t.Fatalf("no denials: %d %v", resp.StatusCode, body)
	}
	f.handle(boxReq("box-a", "", 22))
	f.handle(boxReq("box-b", "2h"))
	resp, body = call(t, "GET", srv.URL+"/v1/denials?host="+url.QueryEscape(u.Host), "")
	ds := body["denials"].([]any)
	if resp.StatusCode != 200 || body["count"].(float64) != 2 || len(ds) != 2 {
		t.Fatalf("two denials: %v", body)
	}
	newest := ds[0].(map[string]any)
	limit := newest["limit"].(map[string]any)
	if limit["name"] != "ttl" || newest["host"] != u.Host || newest["extend_by"] != "operator" ||
		!strings.Contains(newest["extend"].(string), "adeled extend demo ttl 2h") || newest["grant"] != "demo" {
		t.Fatalf("newest = %v", newest)
	}
	// every host
	_, body = call(t, "GET", srv.URL+"/v1/denials", "")
	if body["count"].(float64) != 2 || body["host"] != "" {
		t.Fatalf("all hosts = %v", body)
	}
	// another host has none
	_, body = call(t, "GET", srv.URL+"/v1/denials?host=example.invalid:443", "")
	if body["count"].(float64) != 0 {
		t.Fatalf("other host = %v", body)
	}
	// a request outside the window is not recent
	f.b.Now = func() time.Time { return fixedNow.Add(25 * time.Hour) }
	_, body = call(t, "GET", srv.URL+"/v1/denials", "")
	if body["count"].(float64) != 0 || body["since"] != fixedNow.Add(time.Hour).Format(time.RFC3339) {
		t.Fatalf("after the window = %v", body)
	}
	resp, _ = call(t, "GET", srv.URL+"/v1/denials?host="+strings.Repeat("h", 256), "")
	if resp.StatusCode != 400 {
		t.Fatalf("long host = %d", resp.StatusCode)
	}
	resp, _ = call(t, "POST", srv.URL+"/v1/denials", "{}")
	if resp.StatusCode != 405 {
		t.Fatalf("POST denials = %d", resp.StatusCode)
	}
}

func TestDenialsEndpointLedgerFailure(t *testing.T) {
	f := newFixture(t, demoGrant)
	srv := f.adele(t)
	_ = f.led.Close()
	resp, body := call(t, "GET", srv.URL+"/v1/denials", "")
	if resp.StatusCode != 500 || !strings.Contains(body["error"].(string), "ledger") {
		t.Fatalf("closed ledger: %d %v", resp.StatusCode, body)
	}
}

func TestStandinClientListAndDelete(t *testing.T) {
	f := newFixture(t, demoGrant)
	if out := f.handle(boxReq("box-a", "")); out.Status != 200 {
		t.Fatal(out.Body)
	}
	up := f.b.Upstream.(*StandinClient)
	boxes, err := up.List(context.Background())
	if err != nil || len(boxes) != 1 || boxes[0].Name != "box-a" || boxes[0].TTLSeconds != 3600 ||
		!boxes[0].CreatedAt.Equal(fixedNow) {
		t.Fatalf("list = %+v, %v", boxes, err)
	}
	if err := up.Delete(context.Background(), "box-a"); err != nil {
		t.Fatalf("delete: %v", err)
	}
	if err := up.Delete(context.Background(), "box-a"); !errors.Is(err, ErrNoSuchResource) {
		t.Fatalf("delete again = %v, want ErrNoSuchResource", err)
	}
	wrong := NewStandinClient(f.srv.URL, "tlcanary-ffffffffffffffffffffffffffffffff")
	if err := wrong.Delete(context.Background(), "box-a"); err == nil || errors.Is(err, ErrNoSuchResource) ||
		!strings.Contains(err.Error(), "401") || strings.Contains(err.Error(), "ffffffff") {
		t.Fatalf("wrong canary = %v", err)
	}
	f.srv.Close()
	if _, err := up.List(context.Background()); err == nil {
		t.Fatal("list against a closed stand-in succeeded")
	}
	if h := up.Host(); !strings.HasPrefix(h, "127.0.0.1:") {
		t.Fatalf("host = %q", h)
	}
	if h := (&StandinClient{BaseURL: "::bad"}).Host(); h != "::bad" {
		t.Fatalf("unparsable base host = %q", h)
	}
}
