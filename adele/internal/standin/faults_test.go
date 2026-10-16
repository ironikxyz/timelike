package standin

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func faultFixture(t *testing.T) (*Store, *Faults, http.Handler) {
	t.Helper()
	dir := t.TempDir()
	st, err := NewStore(filepath.Join(dir, "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, n := range []string{"box-a", "box-b"} {
		if err := st.Create(Box{Name: n, CreatedAt: fixedNow, TTLSeconds: 60}); err != nil {
			t.Fatal(err)
		}
	}
	f := NewFaults(filepath.Join(dir, "faults.json"))
	return st, f, HandlerWithFaults(testCanary, st, func() time.Time { return fixedNow }, f)
}

func TestFaultErrorAnswers500AndKeepsTheBoxUntilCleared(t *testing.T) {
	st, f, h := faultFixture(t)
	if err := f.Set("box-a", FaultError); err != nil {
		t.Fatal(err)
	}
	if rec := do(t, h, http.MethodDelete, "/v1/boxes/box-a", bearer, ""); rec.Code != http.StatusInternalServerError ||
		!strings.Contains(rec.Body.String(), "injected fault") {
		t.Fatalf("faulted delete = %d %s", rec.Code, rec.Body)
	}
	if len(st.List()) != 2 {
		t.Fatal("a faulted delete removed the box")
	}
	// Another box is unaffected: faults are per name.
	if rec := do(t, h, http.MethodDelete, "/v1/boxes/box-b", bearer, ""); rec.Code != http.StatusNoContent {
		t.Fatalf("other box = %d", rec.Code)
	}
	if err := f.Set("box-a", FaultClear); err != nil {
		t.Fatal(err)
	}
	if rec := do(t, h, http.MethodDelete, "/v1/boxes/box-a", bearer, ""); rec.Code != http.StatusNoContent {
		t.Fatalf("cleared delete = %d", rec.Code)
	}
	if f.For("box-a") != "" {
		t.Fatal("clear left the fault")
	}
}

func TestFaultDropEndsTheConnectionUnanswered(t *testing.T) {
	st, f, h := faultFixture(t)
	if err := f.Set("box-a", FaultDrop); err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(h)
	defer srv.Close()
	req, _ := http.NewRequest(http.MethodDelete, srv.URL+"/v1/boxes/box-a", nil)
	req.Header.Set("Authorization", bearer)
	resp, err := (&http.Client{Timeout: 5 * time.Second}).Do(req)
	if err == nil {
		resp.Body.Close()
		t.Fatalf("dropped delete answered %d", resp.StatusCode)
	}
	if len(st.List()) != 2 {
		t.Fatal("a dropped delete removed the box")
	}
}

func TestFaultDropWithoutHijackAnswers500(t *testing.T) {
	_, f, h := faultFixture(t)
	_ = f.Set("box-a", FaultDrop)
	if rec := do(t, h, http.MethodDelete, "/v1/boxes/box-a", bearer, ""); rec.Code != http.StatusInternalServerError {
		t.Fatalf("recorder (no hijack) = %d", rec.Code)
	}
}

func TestFaultSetRefusesBadInput(t *testing.T) {
	f := NewFaults(filepath.Join(t.TempDir(), "faults.json"))
	if err := f.Set("Bad Name", FaultError); err == nil {
		t.Error("bad name accepted")
	}
	if err := f.Set("box-a", "explode"); err == nil {
		t.Error("bad mode accepted")
	}
}

func TestFaultFileUnreadableMeansNoFaultAndSetFails(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "faults.json")
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	f := NewFaults(path)
	if f.For("box-a") != "" {
		t.Error("a corrupt file produced a fault")
	}
	if err := f.Set("box-a", FaultError); err == nil {
		t.Error("Set over a corrupt file succeeded")
	}
	var nilFaults *Faults
	if nilFaults.For("box-a") != "" {
		t.Error("nil Faults produced a fault")
	}
}
