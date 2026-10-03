package standin

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"sync"
	"time"
)

// ErrExists is returned by Create when a box of that name is already held.
var ErrExists = errors.New("standin: a box of that name exists")

// ErrNotFound is returned by Delete when no box of that name is held.
var ErrNotFound = errors.New("standin: no box of that name")

// Box is one entry of the stand-in's own record. It is a fake: nothing is
// provisioned anywhere.
type Box struct {
	Name       string    `json:"name"`
	CreatedAt  time.Time `json:"created_at"`
	TTLSeconds int64     `json:"ttl_seconds"`
	Ports      []int     `json:"ports"`
	CostCents  int64     `json:"cost_cents"`
}

// Store is the stand-in's record file: a JSON array of Box, rewritten
// atomically (temp file, fsync, rename) on every change. Tests read it as the
// stand-in's own account of what was performed.
type Store struct {
	mu    sync.Mutex
	path  string
	boxes []Box
}

// NewStore loads the record at path. A missing file is an empty record.
func NewStore(path string) (*Store, error) {
	s := &Store{path: path}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return s, nil
	}
	if err != nil {
		return nil, fmt.Errorf("standin: read record: %w", err)
	}
	if err := json.Unmarshal(data, &s.boxes); err != nil {
		return nil, fmt.Errorf("standin: parse record %s: %w", path, err)
	}
	return s, nil
}

// List returns a copy of the record, sorted by creation time then name.
func (s *Store) List() []Box {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]Box, len(s.boxes))
	for i, b := range s.boxes {
		b.Ports = slices.Clone(b.Ports)
		out[i] = b
	}
	sort.SliceStable(out, func(i, j int) bool {
		if !out[i].CreatedAt.Equal(out[j].CreatedAt) {
			return out[i].CreatedAt.Before(out[j].CreatedAt)
		}
		return out[i].Name < out[j].Name
	})
	return out
}

// Create adds b to the record and persists it. The in-memory record is left
// unchanged if the write fails.
func (s *Store) Create(b Box) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, have := range s.boxes {
		if have.Name == b.Name {
			return ErrExists
		}
	}
	b.Ports = slices.Clone(b.Ports)
	if b.Ports == nil {
		b.Ports = []int{}
	}
	next := append(append([]Box(nil), s.boxes...), b)
	if err := s.write(next); err != nil {
		return err
	}
	s.boxes = next
	return nil
}

// Delete removes the box named name and persists the record.
func (s *Store) Delete(name string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	next := make([]Box, 0, len(s.boxes))
	for _, have := range s.boxes {
		if have.Name != name {
			next = append(next, have)
		}
	}
	if len(next) == len(s.boxes) {
		return ErrNotFound
	}
	if err := s.write(next); err != nil {
		return err
	}
	s.boxes = next
	return nil
}

// write replaces the record file atomically: a temp file in the same
// directory, fsynced, then renamed over the record.
func (s *Store) write(boxes []Box) (err error) {
	if boxes == nil {
		boxes = []Box{}
	}
	data, err := json.MarshalIndent(boxes, "", "  ")
	if err != nil {
		return fmt.Errorf("standin: encode record: %w", err)
	}
	data = append(data, '\n')
	dir := filepath.Dir(s.path)
	tmp, err := os.CreateTemp(dir, "."+filepath.Base(s.path)+".tmp-*")
	if err != nil {
		return fmt.Errorf("standin: write record: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tmp.Close()
			_ = os.Remove(tmp.Name())
		}
	}()
	if _, err = tmp.Write(data); err != nil {
		return fmt.Errorf("standin: write record: %w", err)
	}
	if err = tmp.Sync(); err != nil {
		return fmt.Errorf("standin: sync record: %w", err)
	}
	if err = tmp.Close(); err != nil {
		return fmt.Errorf("standin: close record: %w", err)
	}
	if err = os.Rename(tmp.Name(), s.path); err != nil {
		return fmt.Errorf("standin: replace record: %w", err)
	}
	syncDir(dir)
	return nil
}

// syncDir makes the rename durable where the platform allows it; a failure
// here is not an error, since the rename itself has already succeeded.
func syncDir(dir string) {
	d, err := os.Open(dir)
	if err != nil {
		return
	}
	_ = d.Sync()
	_ = d.Close()
}
