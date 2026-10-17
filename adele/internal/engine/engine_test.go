package engine

import (
	"bytes"
	"encoding/binary"
	"testing"
)

func frame(stream byte, s string) []byte {
	h := make([]byte, 8)
	h[0] = stream
	binary.BigEndian.PutUint32(h[4:], uint32(len(s)))
	return append(h, s...)
}

func TestDemuxSplitsTheDaemonsLogStream(t *testing.T) {
	var b bytes.Buffer
	b.Write(frame(1, `{"ok":`))
	b.Write(frame(2, "warning\n"))
	b.Write(frame(1, `true}`))
	o, e, err := Demux(&b)
	if err != nil || string(o) != `{"ok":true}` || string(e) != "warning\n" {
		t.Fatalf("Demux = %q %q %v", o, e, err)
	}
	cut := frame(1, "abc")[:9]
	if _, _, err := Demux(bytes.NewReader(cut)); err == nil {
		t.Fatal("a cut frame read as complete")
	}
}

func TestCountsTotal(t *testing.T) {
	if (Counts{1, 2, 3}).Total() != 6 {
		t.Fatal("Total")
	}
}
