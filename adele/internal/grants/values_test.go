package grants

import (
	"strings"
	"testing"
	"time"
)

func TestMoney(t *testing.T) {
	good := []struct {
		in    string
		cents int64
		out   string
	}{
		{"2.00 USD", 200, "2.00 USD"},
		{"0.4 USD", 40, "0.40 USD"},
		{"0 USD", 0, "0.00 USD"},
		{"+1.25 USD", 125, "1.25 USD"},
		{"  12.05   USD ", 1205, "12.05 USD"},
	}
	for _, c := range good {
		got, err := ParseMoney(c.in)
		if err != nil || got != c.cents {
			t.Errorf("ParseMoney(%q) = %d, %v; want %d", c.in, got, err, c.cents)
		}
		if f := FormatMoney(got); f != c.out {
			t.Errorf("FormatMoney(%d) = %q, want %q", got, f, c.out)
		}
		if back, _ := ParseMoney(FormatMoney(got)); back != got {
			t.Errorf("round trip of %d gave %d", got, back)
		}
	}
	for _, bad := range []string{"", "USD", "1.000 USD", "-1 USD", "1 usd", "1 EUR", "1.USD", "1.2.3 USD"} {
		if _, err := ParseMoney(bad); err == nil {
			t.Errorf("ParseMoney(%q) succeeded", bad)
		}
	}
	if got := FormatMoney(-5); got != "-0.05 USD" {
		t.Errorf("FormatMoney(-5) = %q", got)
	}
}

func TestTTL(t *testing.T) {
	cases := map[string]time.Duration{"1m": time.Minute, "1h": time.Hour, "90m": 90 * time.Minute,
		"720h": 720 * time.Hour, "1h0m0s": time.Hour}
	for in, want := range cases {
		if got, err := ParseTTL(in); err != nil || got != want {
			t.Errorf("ParseTTL(%q) = %v, %v; want %v", in, got, err, want)
		}
	}
	for _, bad := range []string{"", "59s", "720h0m1s", "-1h", "0", "1 hour"} {
		if _, err := ParseTTL(bad); err == nil {
			t.Errorf("ParseTTL(%q) succeeded", bad)
		}
	}
}

func TestFormatDuration(t *testing.T) {
	cases := map[time.Duration]string{
		time.Hour:                     "1h",
		90 * time.Minute:              "1h30m",
		45 * time.Minute:              "45m",
		720 * time.Hour:               "720h",
		time.Hour + 5*time.Second:     "1h5s",
		61 * time.Second:              "1m1s",
		0:                             "0s",
		1500 * time.Millisecond:       "1.5s",
		2*time.Hour + 3*time.Minute:   "2h3m",
		-time.Minute:                  "-1m0s",
		30*time.Second + time.Hour*24: "24h30s",
	}
	for d, want := range cases {
		got := FormatDuration(d)
		if got != want {
			t.Errorf("FormatDuration(%v) = %q, want %q", d, got, want)
		}
		if back, err := time.ParseDuration(got); err != nil || back != d {
			t.Errorf("ParseDuration(%q) = %v, %v; want %v", got, back, err, d)
		}
	}
}

func TestPorts(t *testing.T) {
	good := map[string]string{
		"8080, 9000-9010": "8080, 9000-9010",
		"22,80":           "22, 80",
		" none ":          "none",
		"1-65535":         "1-65535",
		"9000 - 9000":     "9000",
	}
	for in, want := range good {
		ps, err := ParsePorts(in)
		if err != nil || ps.String() != want {
			t.Errorf("ParsePorts(%q) = %q, %v; want %q", in, ps, err, want)
			continue
		}
		if again, _ := ParsePorts(ps.String()); again.String() != want {
			t.Errorf("round trip of %q gave %q", want, again)
		}
	}
	for _, bad := range []string{"", "0", "65536", "80,", "9010-9000", "a-b", "none, 80", "1-2-3"} {
		if _, err := ParsePorts(bad); err == nil {
			t.Errorf("ParsePorts(%q) succeeded", bad)
		}
	}
	ps, _ := ParsePorts("8080, 9000-9010")
	for p, want := range map[int]bool{8080: true, 9000: true, 9005: true, 9010: true, 8081: false, 9011: false, 22: false} {
		if ps.Contains(p) != want {
			t.Errorf("Contains(%d) = %v", p, !want)
		}
	}
	if (PortSet{}).Contains(80) {
		t.Error("none contains 80")
	}
}

func TestErrorTextHasFix(t *testing.T) {
	_, err := ParsePorts("0")
	if err == nil || !strings.Contains(err.Error(), " — a port is from 1 to 65535") {
		t.Errorf("err = %v", err)
	}
}
