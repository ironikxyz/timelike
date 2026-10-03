package standin

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestStorePersistsAcrossReopen(t *testing.T) {
	path := filepath.Join(t.TempDir(), "boxes.json")
	st, err := NewStore(path)
	if err != nil {
		t.Fatal(err)
	}
	b1 := Box{Name: "b", CreatedAt: fixedNow, TTLSeconds: 60, Ports: []int{1}, CostCents: 1}
	b2 := Box{Name: "a", CreatedAt: fixedNow, TTLSeconds: 120, Ports: []int{}, CostCents: 1}
	b3 := Box{Name: "c", CreatedAt: fixedNow.Add(-time.Hour), TTLSeconds: 60, Ports: []int{}, CostCents: 1}
	for _, b := range []Box{b1, b2, b3} {
		if err := st.Create(b); err != nil {
			t.Fatal(err)
		}
	}
	if err := st.Delete("b"); err != nil {
		t.Fatal(err)
	}
	re, err := NewStore(path)
	if err != nil {
		t.Fatal(err)
	}
	got, _ := json.Marshal(re.List())
	want, _ := json.Marshal([]Box{b3, b2})
	if string(got) != string(want) {
		t.Fatalf("reopened = %s, want %s", got, want)
	}
}

func TestStoreSortsByCreationThenName(t *testing.T) {
	st, err := NewStore(filepath.Join(t.TempDir(), "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, b := range []Box{
		{Name: "z", CreatedAt: fixedNow}, {Name: "y", CreatedAt: fixedNow}, {Name: "x", CreatedAt: fixedNow.Add(time.Minute)},
	} {
		if err := st.Create(b); err != nil {
			t.Fatal(err)
		}
	}
	var names []string
	for _, b := range st.List() {
		names = append(names, b.Name)
	}
	if strings.Join(names, ",") != "y,z,x" {
		t.Fatalf("order = %v", names)
	}
}

func TestStoreErrors(t *testing.T) {
	st, err := NewStore(filepath.Join(t.TempDir(), "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err := st.Create(Box{Name: "a"}); err != nil {
		t.Fatal(err)
	}
	if err := st.Create(Box{Name: "a"}); !errors.Is(err, ErrExists) {
		t.Fatalf("duplicate: %v", err)
	}
	if err := st.Delete("nope"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("missing: %v", err)
	}
}

func TestStoreListIsACopy(t *testing.T) {
	st, err := NewStore(filepath.Join(t.TempDir(), "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	ports := []int{80}
	if err := st.Create(Box{Name: "a", Ports: ports}); err != nil {
		t.Fatal(err)
	}
	ports[0] = 1
	st.List()[0].Ports[0] = 2
	if p := st.List()[0].Ports[0]; p != 80 {
		t.Fatalf("store aliased caller memory: port %d", p)
	}
}

func TestStoreAtomicWriteLeavesNoTempFiles(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "boxes.json")
	st, err := NewStore(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, n := range []string{"a", "b", "c"} {
		if err := st.Create(Box{Name: n}); err != nil {
			t.Fatal(err)
		}
	}
	if err := st.Delete("b"); err != nil {
		t.Fatal(err)
	}
	if err := st.Delete("a"); err != nil {
		t.Fatal(err)
	}
	if err := st.Delete("c"); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != "boxes.json" {
		var names []string
		for _, e := range entries {
			names = append(names, e.Name())
		}
		t.Fatalf("directory holds %v", names)
	}
	if data, _ := os.ReadFile(path); strings.TrimSpace(string(data)) != "[]" {
		t.Fatalf("emptied record = %q", data)
	}
}

func TestStoreWriteFailureLeavesRecordUnchanged(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "boxes.json")
	st, err := NewStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := st.Create(Box{Name: "a"}); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o500); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(dir, 0o700) })
	if err := st.Create(Box{Name: "b"}); err == nil {
		t.Fatal("create into a read-only directory succeeded")
	}
	if err := st.Delete("a"); err == nil {
		t.Fatal("delete in a read-only directory succeeded")
	}
	if got := st.List(); len(got) != 1 || got[0].Name != "a" {
		t.Fatalf("in-memory record changed: %+v", got)
	}
}

func TestNewStoreErrors(t *testing.T) {
	dir := t.TempDir()
	bad := filepath.Join(dir, "bad.json")
	if err := os.WriteFile(bad, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewStore(bad); err == nil {
		t.Fatal("malformed record accepted")
	}
	if _, err := NewStore(dir); err == nil {
		t.Fatal("a directory accepted as the record")
	}
}

func TestReadCanary(t *testing.T) {
	dir := t.TempDir()
	write := func(name, content string) string {
		p := filepath.Join(dir, name)
		if err := os.WriteFile(p, []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
		return p
	}
	for _, content := range []string{testCanary, testCanary + "\n", testCanary + "\r\n"} {
		got, err := ReadCanary(write("ok", content))
		if err != nil || got != testCanary {
			t.Fatalf("ReadCanary(%q) = %q, %v", content, got, err)
		}
	}
	invalid := map[string]string{
		"empty":       "",
		"blank":       " \n",
		"upper hex":   "tlcanary-0123456789ABCDEF0123456789abcdef",
		"short":       "tlcanary-0123456789abcdef",
		"long":        testCanary + "00",
		"wrong label": "sk-live-0123456789abcdef0123456789abcdef",
		"two lines":   testCanary + "\n" + testCanary,
		"oversized":   "secretpayload-" + strings.Repeat("q", 5000),
	}
	for label, content := range invalid {
		_, err := ReadCanary(write(label, content))
		if err == nil {
			t.Errorf("%s: accepted", label)
			continue
		}
		if strings.Contains(err.Error(), "0123456789abcdef") || strings.Contains(err.Error(), "sk-live") || strings.Contains(err.Error(), "secretpayload") {
			t.Errorf("%s: error %q contains the file's content", label, err)
		}
	}
	if _, err := ReadCanary(filepath.Join(dir, "missing")); err == nil {
		t.Fatal("missing file accepted")
	}
	if _, err := ReadCanary(dir); err == nil {
		t.Fatal("a directory accepted")
	}
}
