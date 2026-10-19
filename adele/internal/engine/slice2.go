package engine

// Feature 13 slice 2 (014 plan § Slice 2, R23, R25-R28): snapshot volumes Adele creates and removes, and the pause,
// unpause, stop and start a snapshot or restore puts on an environment's services. The host's standing rule still
// holds: every volume created here carries timelike's environment label, and every container paused, stopped or
// started was found by one.

import (
	"context"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// Labels slice 2 adds (014 data-model § Slice 2).
const (
	LabelSnapshot   = LabelPrefix + "snapshot"    // the snapshot's id, s-<8 hex>
	LabelSnapshotOf = LabelPrefix + "snapshot-of" // the daemon name of the volume it was taken from
	// SandboxVolume is the volume helper's sandbox label value; the sweep removes every kind.
	SandboxVolume = "volume"
)

// HelperCaps are the volume helper's capabilities, each for one reason (R25): owners and groups (CHOWN), reading
// whatever the modes (DAC_READ_SEARCH), writing into a directory it already gave to another owner (DAC_OVERRIDE),
// modes and times on entries it does not own (FOWNER), and a setgid or setuid bit kept after the owner changes
// (FSETID). Not MKNOD: it makes no device nodes.
var HelperCaps = []string{"CHOWN", "DAC_READ_SEARCH", "DAC_OVERRIDE", "FOWNER", "FSETID"}

func nonNilList(l []string) []string {
	if l == nil {
		return []string{}
	}
	return l
}

// CreateVolume creates a local volume named name with labels and driver options (a tmpfs store's, or none).
func (c *Client) CreateVolume(ctx context.Context, name string, labels, opts map[string]string) error {
	if opts == nil {
		opts = map[string]string{}
	}
	return c.do(ctx, http.MethodPost, "/volumes/create", map[string]any{"Name": name, "Driver": "local",
		"DriverOpts": opts, "Labels": nonNil(labels)}, nil, http.StatusCreated)
}

// RemoveVolume removes the volume name. One already gone is removed.
func (c *Client) RemoveVolume(ctx context.Context, name string) error {
	return c.do(ctx, http.MethodDelete, "/volumes/"+url.PathEscape(name), nil, nil, http.StatusNoContent,
		http.StatusNotFound)
}

// VolumeExists inspects the volume name: its labels, and whether the daemon has it.
func (c *Client) VolumeExists(ctx context.Context, name string) (map[string]string, bool, error) {
	var v Object
	err := c.do(ctx, http.MethodGet, "/volumes/"+url.PathEscape(name), nil, &v, http.StatusOK)
	if IsNotFound(err) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return v.Labels, true, nil
}

// Pause and Unpause freeze and thaw a labelled container. A container already in that state is not an error: the
// caller reads the state back either way (cross-stack P004).
func (c *Client) Pause(ctx context.Context, id string) error {
	return c.do(ctx, http.MethodPost, "/containers/"+url.PathEscape(id)+"/pause", nil, nil, http.StatusNoContent,
		http.StatusConflict)
}

// Unpause thaws a container Pause froze.
func (c *Client) Unpause(ctx context.Context, id string) error {
	return c.do(ctx, http.MethodPost, "/containers/"+url.PathEscape(id)+"/unpause", nil, nil, http.StatusNoContent,
		http.StatusConflict)
}

// Stop stops a labelled container, giving it wait to exit before it is killed.
func (c *Client) Stop(ctx context.Context, id string, wait time.Duration) error {
	return c.do(ctx, http.MethodPost, "/containers/"+url.PathEscape(id)+"/stop?t="+strconv.Itoa(int(wait/time.Second)),
		nil, nil, http.StatusNoContent, http.StatusNotModified)
}

// Start starts a labelled container. One already running is not an error.
func (c *Client) Start(ctx context.Context, id string) error {
	return c.do(ctx, http.MethodPost, "/containers/"+url.PathEscape(id)+"/start", nil, nil, http.StatusNoContent,
		http.StatusNotModified)
}

// State reads one labelled container's state back: running, paused, exited, … or "removed" when the daemon no
// longer has it.
func (c *Client) State(ctx context.Context, id string) (string, error) {
	var in struct {
		State struct {
			Status string `json:"Status"`
		} `json:"State"`
	}
	err := c.do(ctx, http.MethodGet, "/containers/"+url.PathEscape(id)+"/json", nil, &in, http.StatusOK)
	if IsNotFound(err) {
		return "removed", nil
	}
	return in.State.Status, err
}
