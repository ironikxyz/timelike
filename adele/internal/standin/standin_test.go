package standin

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

const testCanary = "tlcanary-0123456789abcdef0123456789abcdef"

var fixedNow = time.Date(2026, 10, 2, 12, 0, 0, 0, time.UTC)

func newFixture(t *testing.T, canary string) (*Store, http.Handler, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "boxes.json")
	st, err := NewStore(path)
	if err != nil {
		t.Fatal(err)
	}
	return st, Handler(canary, st, func() time.Time { return fixedNow }), path
}

func do(t *testing.T, h http.Handler, method, target, auth, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, target, strings.NewReader(body))
	if auth != "" {
		req.Header.Set("Authorization", auth)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

const bearer = "Bearer " + testCanary

func decodeBody(t *testing.T, rec *httptest.ResponseRecorder, v any) {
	t.Helper()
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Fatalf("Content-Type = %q", ct)
	}
	if err := json.Unmarshal(rec.Body.Bytes(), v); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
}

func readRecord(t *testing.T, path string) []byte {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil && !os.IsNotExist(err) {
		t.Fatal(err)
	}
	return b
}

func TestPrice(t *testing.T) {
	cases := []struct {
		ttl  time.Duration
		want int64
	}{
		{0, 0}, {time.Second, 1}, {time.Minute, 1}, {2 * time.Minute, 1}, {3 * time.Minute, 2},
		{60 * time.Minute, 25}, {61 * time.Minute, 26}, {90 * time.Minute, 38},
		{2 * time.Hour, 50}, {30 * 24 * time.Hour, 18000},
	}
	for _, c := range cases {
		if got := Price(c.ttl); got != c.want {
			t.Errorf("Price(%v) = %d, want %d", c.ttl, got, c.want)
		}
	}
}

func TestQuote(t *testing.T) {
	_, h, path := newFixture(t, testCanary)
	rec := do(t, h, http.MethodPost, "/v1/quote", bearer, `{"ttl_seconds":3600}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	var got map[string]int64
	decodeBody(t, rec, &got)
	if got["cost_cents"] != 25 {
		t.Fatalf("cost_cents = %d", got["cost_cents"])
	}
	if readRecord(t, path) != nil {
		t.Fatal("a quote wrote the record")
	}
}

func TestCreateListDelete(t *testing.T) {
	st, h, _ := newFixture(t, testCanary)
	rec := do(t, h, http.MethodPost, "/v1/boxes", bearer, `{"name":"web-1","ttl_seconds":5400,"ports":[8080,9000]}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("create status %d: %s", rec.Code, rec.Body)
	}
	var created struct {
		Name      string    `json:"name"`
		CreatedAt time.Time `json:"created_at"`
		CostCents int64     `json:"cost_cents"`
	}
	decodeBody(t, rec, &created)
	if created.Name != "web-1" || !created.CreatedAt.Equal(fixedNow) || created.CostCents != 38 {
		t.Fatalf("created = %+v", created)
	}

	rec = do(t, h, http.MethodGet, "/v1/boxes", bearer, "")
	if rec.Code != http.StatusOK {
		t.Fatalf("list status %d", rec.Code)
	}
	var boxes []Box
	decodeBody(t, rec, &boxes)
	want := []Box{{Name: "web-1", CreatedAt: fixedNow, TTLSeconds: 5400, Ports: []int{8080, 9000}, CostCents: 38}}
	if !reflect.DeepEqual(boxes, want) {
		t.Fatalf("list = %+v", boxes)
	}

	rec = do(t, h, http.MethodDelete, "/v1/boxes/web-1", bearer, "")
	if rec.Code != http.StatusNoContent {
		t.Fatalf("delete status %d: %s", rec.Code, rec.Body)
	}
	if n := len(st.List()); n != 0 {
		t.Fatalf("%d boxes after delete", n)
	}
}

func TestListEmptyIsArray(t *testing.T) {
	_, h, _ := newFixture(t, testCanary)
	rec := do(t, h, http.MethodGet, "/v1/boxes", bearer, "")
	if strings.TrimSpace(rec.Body.String()) != "[]" {
		t.Fatalf("empty list body = %q", rec.Body)
	}
}

func TestCreateWithoutPortsRecordsEmptyList(t *testing.T) {
	st, h, _ := newFixture(t, testCanary)
	if rec := do(t, h, http.MethodPost, "/v1/boxes", bearer, `{"name":"a","ttl_seconds":60}`); rec.Code != http.StatusCreated {
		t.Fatalf("status %d", rec.Code)
	}
	if p := st.List()[0].Ports; p == nil || len(p) != 0 {
		t.Fatalf("ports = %#v", p)
	}
}

// TestRefusal is FR-20, tested directly against the stand-in: every request
// without the canary is refused with 401 and nothing changes.
func TestRefusal(t *testing.T) {
	auths := map[string]string{
		"no header":   "",
		"wrong token": "Bearer tlcanary-ffffffffffffffffffffffffffffffff",
		"prefix only": "Bearer " + testCanary[:20],
		"basic":       "Basic " + testCanary,
		"lower case":  "bearer " + testCanary,
		"bare token":  testCanary,
	}
	requests := []struct{ method, target, body string }{
		{http.MethodPost, "/v1/boxes", `{"name":"new","ttl_seconds":60,"ports":[]}`},
		{http.MethodDelete, "/v1/boxes/held", ""},
		{http.MethodPost, "/v1/quote", `{"ttl_seconds":60}`},
		{http.MethodGet, "/v1/boxes", ""},
		{http.MethodGet, "/nowhere", ""},
	}
	for label, auth := range auths {
		for _, r := range requests {
			assertRefused(t, testCanary, label, auth, r.method, r.target, r.body)
		}
	}
	for _, r := range requests {
		assertRefused(t, "", "empty canary", "Bearer ", r.method, r.target, r.body)
		assertRefused(t, "", "empty canary, no header", "", r.method, r.target, r.body)
	}
}

func assertRefused(t *testing.T, canary, label, auth, method, target, body string) {
	t.Helper()
	st, h, path := newFixture(t, canary)
	if err := st.Create(Box{Name: "held", CreatedAt: fixedNow, TTLSeconds: 60, Ports: []int{}, CostCents: 1}); err != nil {
		t.Fatal(err)
	}
	before := readRecord(t, path)
	rec := do(t, h, method, target, auth, body)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("%s %s %s: status %d", label, method, target, rec.Code)
	}
	var got map[string]string
	decodeBody(t, rec, &got)
	if got["error"] != "missing or wrong credential" {
		t.Fatalf("%s: body %q", label, rec.Body)
	}
	if strings.Contains(rec.Body.String(), "tlcanary") {
		t.Fatalf("%s: response echoes a credential", label)
	}
	if after := readRecord(t, path); string(after) != string(before) {
		t.Fatalf("%s %s %s: record changed", label, method, target)
	}
	if boxes := st.List(); len(boxes) != 1 || boxes[0].Name != "held" {
		t.Fatalf("%s %s %s: store changed: %+v", label, method, target, boxes)
	}
}

func TestDuplicateIs409(t *testing.T) {
	st, h, _ := newFixture(t, testCanary)
	body := `{"name":"dup","ttl_seconds":60,"ports":[22]}`
	if rec := do(t, h, http.MethodPost, "/v1/boxes", bearer, body); rec.Code != http.StatusCreated {
		t.Fatalf("first create %d", rec.Code)
	}
	rec := do(t, h, http.MethodPost, "/v1/boxes", bearer, `{"name":"dup","ttl_seconds":120,"ports":[]}`)
	if rec.Code != http.StatusConflict {
		t.Fatalf("duplicate status %d", rec.Code)
	}
	if b := st.List(); len(b) != 1 || b[0].TTLSeconds != 60 {
		t.Fatalf("store after duplicate = %+v", b)
	}
}

func TestDeleteMissingIs404(t *testing.T) {
	_, h, _ := newFixture(t, testCanary)
	rec := do(t, h, http.MethodDelete, "/v1/boxes/ghost", bearer, "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status %d", rec.Code)
	}
	var got map[string]string
	decodeBody(t, rec, &got)
	if got["error"] == "" {
		t.Fatal("no error text")
	}
}

func TestBadRequests(t *testing.T) {
	cases := []struct{ name, method, target, body string }{
		{"quote ttl low", http.MethodPost, "/v1/quote", `{"ttl_seconds":59}`},
		{"quote ttl high", http.MethodPost, "/v1/quote", `{"ttl_seconds":2592001}`},
		{"quote not json", http.MethodPost, "/v1/quote", `nope`},
		{"quote unknown field", http.MethodPost, "/v1/quote", `{"ttl_seconds":60,"x":1}`},
		{"quote trailing", http.MethodPost, "/v1/quote", `{"ttl_seconds":60}{}`},
		{"quote empty", http.MethodPost, "/v1/quote", ``},
		{"name upper", http.MethodPost, "/v1/boxes", `{"name":"Web","ttl_seconds":60,"ports":[]}`},
		{"name digit first", http.MethodPost, "/v1/boxes", `{"name":"1web","ttl_seconds":60,"ports":[]}`},
		{"name empty", http.MethodPost, "/v1/boxes", `{"name":"","ttl_seconds":60,"ports":[]}`},
		{"name too long", http.MethodPost, "/v1/boxes", `{"name":"a` + strings.Repeat("b", 63) + `","ttl_seconds":60,"ports":[]}`},
		{"box ttl", http.MethodPost, "/v1/boxes", `{"name":"a","ttl_seconds":0,"ports":[]}`},
		{"port zero", http.MethodPost, "/v1/boxes", `{"name":"a","ttl_seconds":60,"ports":[0]}`},
		{"port high", http.MethodPost, "/v1/boxes", `{"name":"a","ttl_seconds":60,"ports":[65536]}`},
		{"ports not ints", http.MethodPost, "/v1/boxes", `{"name":"a","ttl_seconds":60,"ports":["80"]}`},
		{"delete bad name", http.MethodDelete, "/v1/boxes/Bad_Name", ``},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			st, h, path := newFixture(t, testCanary)
			rec := do(t, h, c.method, c.target, bearer, c.body)
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status %d: %s", rec.Code, rec.Body)
			}
			var got map[string]string
			decodeBody(t, rec, &got)
			if got["error"] == "" {
				t.Fatal("no error text")
			}
			if len(st.List()) != 0 || readRecord(t, path) != nil {
				t.Fatal("a bad request changed the record")
			}
		})
	}
}

func TestBodyLimit(t *testing.T) {
	_, h, _ := newFixture(t, testCanary)
	body := `{"name":"a","ttl_seconds":60,"ports":[` + strings.Repeat("80,", MaxBodyBytes/3) + `80]}`
	rec := do(t, h, http.MethodPost, "/v1/boxes", bearer, body)
	if rec.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestMethodAndPath(t *testing.T) {
	cases := []struct {
		method, target string
		want           int
		allow          string
	}{
		{http.MethodGet, "/v1/quote", http.StatusMethodNotAllowed, "POST"},
		{http.MethodDelete, "/v1/boxes", http.StatusMethodNotAllowed, "GET, POST"},
		{http.MethodGet, "/v1/boxes/a", http.StatusMethodNotAllowed, "DELETE"},
		{http.MethodPut, "/v1/boxes/a", http.StatusMethodNotAllowed, "DELETE"},
		{http.MethodGet, "/", http.StatusNotFound, ""},
		{http.MethodGet, "/v1/box", http.StatusNotFound, ""},
		{http.MethodPost, "/v2/quote", http.StatusNotFound, ""},
	}
	for _, c := range cases {
		_, h, _ := newFixture(t, testCanary)
		rec := do(t, h, c.method, c.target, bearer, "")
		if rec.Code != c.want {
			t.Errorf("%s %s: status %d, want %d", c.method, c.target, rec.Code, c.want)
		}
		if got := rec.Header().Get("Allow"); got != c.allow {
			t.Errorf("%s %s: Allow %q, want %q", c.method, c.target, got, c.allow)
		}
		var body map[string]string
		decodeBody(t, rec, &body)
	}
}

func TestNilNowUsesClock(t *testing.T) {
	st, err := NewStore(filepath.Join(t.TempDir(), "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	h := Handler(testCanary, st, nil)
	before := time.Now().Add(-time.Second)
	if rec := do(t, h, http.MethodPost, "/v1/boxes", bearer, `{"name":"a","ttl_seconds":60,"ports":[]}`); rec.Code != http.StatusCreated {
		t.Fatalf("status %d", rec.Code)
	}
	if got := st.List()[0].CreatedAt; got.Before(before) || got.Location() != time.UTC {
		t.Fatalf("created_at = %v", got)
	}
}
