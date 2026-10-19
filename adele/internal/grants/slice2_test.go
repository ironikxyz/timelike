package grants

import (
	"strings"
	"testing"
)

// Feature 13 slice 2 (014 plan R29): `snapshots` and `snapshot-store` are optional; absent, they are 1 GiB and
// volume. `snapshots` extends like a number; `snapshot-store` does not extend.
func TestSnapshotKeys(t *testing.T) {
	f, err := Parse("g", strings.NewReader(validGrant+"snapshots = 64KiB\nsnapshot-store = tmpfs\n"))
	if err != nil {
		t.Fatal(err)
	}
	if g := f.Grants[0]; g.SnapshotBytes != 64<<10 || g.SnapshotStore != StoreTmpfs {
		t.Fatalf("got %d %q", g.SnapshotBytes, g.SnapshotStore)
	}
	for _, c := range []struct{ src, want string }{
		{validGrant + "snapshots = 64\n", "has no unit"},
		{validGrant + "snapshots = 1TB\n", "unparsable size"},
		{validGrant + "snapshots = -1GiB\n", "unparsable size"},
		{validGrant + "snapshots = 99999999999999GiB\n", "too large"},
		{validGrant + "snapshot-store = disk\n", "unknown snapshot-store"},
		{validGrant + "snapshots = 1GiB\nsnapshots = 2GiB\n", "duplicate key"},
		{validGrant + "snapshot = 1GiB\n", "optionally snapshots and snapshot-store"},
	} {
		if _, err := Parse("g", strings.NewReader(c.src)); err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%q: %v, want %q", c.src, err, c.want)
		}
	}
	g, _ := f.Get("demo")
	ext, err := Effective(g, []Extension{{Grant: "demo", Limit: LimitSnapshots, Value: "2GiB"}})
	if err != nil || ext.SnapshotBytes != 2<<30 || FormatLimit(ext, LimitSnapshots) != "2GiB" {
		t.Fatalf("extended: %d %v", ext.SnapshotBytes, err)
	}
	if err := ValidateExtension(LimitSnapshots, "2GiB"); err != nil {
		t.Fatalf("adeled extend GRANT snapshots 2GiB is refused: %v", err)
	}
	if _, err := Effective(g, []Extension{{Grant: "demo", Limit: KeySnapshotStore, Value: "volume"}}); err == nil {
		t.Fatal("snapshot-store extended; it is not a limit")
	}
}

func TestSizes(t *testing.T) {
	for in, want := range map[string]int64{"0": 0, "512B": 512, "64KiB": 64 << 10, "256MiB": 256 << 20, "1GiB": 1 << 30,
		"1 GiB": 1 << 30} {
		if n, err := ParseSize(in); err != nil || n != want {
			t.Errorf("ParseSize(%q) = %d, %v; want %d", in, n, err, want)
		}
	}
	if _, err := ParseSize("x"); err == nil {
		t.Error("ParseSize(x) passed")
	}
	for n, want := range map[int64]string{0: "0", 1 << 30: "1GiB", 300 << 20: "300MiB", 1500: "1500B", 2048: "2KiB"} {
		if got := FormatSize(n); got != want {
			t.Errorf("FormatSize(%d) = %q, want %q", n, got, want)
		}
	}
	for n, want := range map[int64]string{512: "512 B", 49152: "48 KiB", 49200: "48.0 KiB", 1 << 30: "1 GiB",
		(1 << 30) + (1 << 29): "1.5 GiB"} {
		if got := HumanSize(n); got != want {
			t.Errorf("HumanSize(%d) = %q, want %q", n, got, want)
		}
	}
}
