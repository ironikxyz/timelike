package broker

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

func (f *fixture) adele(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(f.b.Handler())
	t.Cleanup(srv.Close)
	return srv
}

func call(t *testing.T, method, url, body string) (*http.Response, map[string]any) {
	t.Helper()
	req, err := http.NewRequest(method, url, strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		t.Fatalf("%s %s: body is not a JSON object: %q", method, url, data)
	}
	if ct := resp.Header.Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q", ct)
	}
	return resp, out
}

func TestHTTPHealth(t *testing.T) {
	f := newFixture(t, twoGrants)
	resp, body := call(t, "GET", f.adele(t).URL+"/v1/health", "")
	if resp.StatusCode != 200 || body["service"] != "adele" || body["revision"] != "rev-test" ||
		!reflect.DeepEqual(body["grants"], []any{"alpha", "beta"}) {
		t.Errorf("got %d %v", resp.StatusCode, body)
	}
}

// /v1/grants shows the effective grant (after extensions), what is spent and what is live.
func TestHTTPGrants(t *testing.T) {
	f := newFixture(t, demoGrant)
	f.mustPerform(t, boxReq("a", ""))
	for _, e := range [][3]string{{"ttl", "1h", "2h"}, {"ports", "8080", "22"}} {
		if _, err := f.led.Extended("demo", e[0], e[1], e[2], fixedNow); err != nil {
			t.Fatal(err)
		}
	}
	resp, body := call(t, "GET", f.adele(t).URL+"/v1/grants", "")
	list := body["grants"].([]any)
	if resp.StatusCode != 200 || len(list) != 1 {
		t.Fatalf("got %d %v", resp.StatusCode, body)
	}
	g := list[0].(map[string]any)
	want := map[string]any{"name": "demo", "budget_cents": 100.0, "spent_cents": 25.0, "ttl": "2h",
		"instances": 2.0, "live": 1.0, "ports": "8080, 22", "capabilities": []any{"standin.box"}}
	for k, v := range want {
		if !reflect.DeepEqual(g[k], v) {
			t.Errorf("grants[0].%s = %#v, want %#v", k, g[k], v)
		}
	}
}

func TestHTTPGrantsFailures(t *testing.T) {
	t.Run("damaged ledger", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.sabotageLedgerTable(t)
		resp, body := call(t, "GET", f.adele(t).URL+"/v1/grants", "")
		if resp.StatusCode != 500 || !strings.Contains(body["error"].(string), "the ledger failed") {
			t.Errorf("got %d %v", resp.StatusCode, body)
		}
	})
	t.Run("extension that does not apply", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		if _, err := f.led.Extended("demo", "ttl", "1h", "forever", fixedNow); err != nil {
			t.Fatal(err)
		}
		if resp, body := call(t, "GET", f.adele(t).URL+"/v1/grants", ""); resp.StatusCode != 500 {
			t.Errorf("got %d %v", resp.StatusCode, body)
		}
	})
}

func TestHTTPRequestRoundTrip(t *testing.T) {
	f := newFixture(t, demoGrant)
	srv := f.adele(t)
	resp, body := call(t, "POST", srv.URL+"/v1/requests",
		`{"session":"s1","capability":"standin.box","action":"create","params":{"name":"web","ttl":"30m","ports":[8080]}}`)
	if resp.StatusCode != 200 || body["outcome"] != "performed" || body["resource"] != "web" || body["cost_cents"] != 13.0 {
		t.Fatalf("got %d %v", resp.StatusCode, body)
	}
	if _, ok := f.hasBox("web"); !ok {
		t.Errorf("the stand-in has no web")
	}
	resp, body = call(t, "POST", srv.URL+"/v1/requests",
		`{"session":"s1","grant":null,"capability":"standin.box","action":"create","params":{"name":"web2","ttl":"2h"}}`)
	if resp.StatusCode != 403 || body["performed"] != false {
		t.Errorf("got %d %v", resp.StatusCode, body)
	}
}

func TestHTTPRequestBadBodies(t *testing.T) {
	big := `{"session":"s1","capability":"standin.box","action":"create","params":{"name":"` +
		strings.Repeat("a", MaxBodyBytes) + `"}}`
	cases := map[string]string{
		"malformed":     `{"session":`,
		"unknown field": `{"session":"s1","capability":"standin.box","action":"create","params":{"name":"a"},"bogus":1}`,
		"not an object": `[1,2]`,
		"over 64 KiB":   big,
	}
	for name, raw := range cases {
		t.Run(name, func(t *testing.T) {
			f := newFixture(t, demoGrant)
			resp, body := call(t, "POST", f.adele(t).URL+"/v1/requests", raw)
			if resp.StatusCode != 400 || !strings.Contains(body["error"].(string), "not valid JSON") {
				t.Errorf("got %d %v", resp.StatusCode, body)
			}
			assertNothing(t, f)
		})
	}
}

func TestHTTPMethodsAndPaths(t *testing.T) {
	f := newFixture(t, demoGrant)
	srv := f.adele(t)
	for _, c := range []struct{ method, path, allow string }{
		{"POST", "/v1/health", "GET"}, {"DELETE", "/v1/grants", "GET"}, {"GET", "/v1/requests", "POST"},
	} {
		resp, body := call(t, c.method, srv.URL+c.path, "")
		if resp.StatusCode != 405 || resp.Header.Get("Allow") != c.allow || body["error"] != "use "+c.allow {
			t.Errorf("%s %s: got %d Allow=%q %v", c.method, c.path, resp.StatusCode, resp.Header.Get("Allow"), body)
		}
	}
	resp, body := call(t, "GET", srv.URL+"/v2/nothing", "")
	if resp.StatusCode != 404 || body["error"] != "no such path" {
		t.Errorf("unknown path: got %d %v", resp.StatusCode, body)
	}
	assertNothing(t, f)
}

func TestRedact(t *testing.T) {
	if got := redact("token "+testCanary+" and "+testCanary, testCanary); got != "token [REDACTED:credential] and [REDACTED:credential]" {
		t.Errorf("redact = %q", got)
	}
	if got := redact("token x", ""); got != "token x" {
		t.Errorf("empty canary changed the text: %q", got)
	}
}
