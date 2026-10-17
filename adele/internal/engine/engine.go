// Package engine is Adele's client for the local Docker Engine API, over the unix socket only she holds
// (feature 13, slice 0; 014 research R2, R4, R6). It is stdlib net/http with a unix dialer.
//
// The host's standing rule: timelike creates and removes only its own containers and images. So every list
// here is filtered by one of timelike's labels, and nothing is inspected, stopped or removed that was not
// found by such a list, except the sandbox container this package itself created, and images, which are
// only inspected (never pulled or removed).
package engine

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Labels timelike puts on what Adele creates.
const (
	LabelPrefix  = "xyz.ironik.timelike."
	LabelEnv     = LabelPrefix + "env"
	LabelCreated = LabelPrefix + "created"
	LabelTTL     = LabelPrefix + "ttl-seconds"
	LabelModel   = LabelPrefix + "model"
	LabelPorts   = LabelPrefix + "ports"
	LabelSandbox = LabelPrefix + "sandbox"
	LabelNetwork = LabelPrefix + "network"
	// ComposeService is compose's own label naming a container's service.
	ComposeService = "com.docker.compose.service"
)

// MaxOutput bounds what is read from a sandbox's logs or an API answer.
const MaxOutput = 8 << 20

// Client talks to the daemon at a unix socket.
type Client struct {
	Socket string
	http   *http.Client
}

// New returns a client for the socket at path.
func New(path string) *Client {
	tr := &http.Transport{
		DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
			var d net.Dialer
			return d.DialContext(ctx, "unix", path)
		},
		MaxIdleConns: 4, IdleConnTimeout: 30 * time.Second,
	}
	return &Client{Socket: path, http: &http.Client{Transport: tr}}
}

// Host is what a refusal records as where the request would have reached (004 FR-35).
func (c *Client) Host() string { return "docker:local" }

// APIError is a daemon answer with an unexpected status.
type APIError struct {
	Status  int
	Message string
	Path    string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("the Docker daemon answered %d to %s: %s", e.Status, e.Path, e.Message)
}

// IsNotFound reports a 404 from the daemon.
func IsNotFound(err error) bool {
	var ae *APIError
	return errors.As(err, &ae) && ae.Status == http.StatusNotFound
}

func (c *Client) do(ctx context.Context, method, path string, body any, out any, ok ...int) error {
	var rd io.Reader
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return err
		}
		rd = bytes.NewReader(raw)
	}
	req, err := http.NewRequestWithContext(ctx, method, "http://docker"+path, rd)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("cannot reach the Docker daemon at %s from Adele's container: %w", c.Socket, err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, MaxOutput))
	good := false
	for _, s := range ok {
		good = good || resp.StatusCode == s
	}
	if !good {
		var m struct {
			Message string `json:"message"`
		}
		_ = json.Unmarshal(data, &m)
		if m.Message == "" {
			m.Message = strings.TrimSpace(string(data))
		}
		return &APIError{Status: resp.StatusCode, Message: m.Message, Path: strings.SplitN(path, "?", 2)[0]}
	}
	if out != nil && len(data) > 0 {
		if err := json.Unmarshal(data, out); err != nil {
			return fmt.Errorf("the Docker daemon's answer to %s is not readable JSON: %w", path, err)
		}
	}
	return nil
}

func labelFilter(labels ...string) string {
	raw, _ := json.Marshal(map[string][]string{"label": labels})
	return url.QueryEscape(string(raw))
}

// ImageExists inspects an image by reference. It never pulls.
func (c *Client) ImageExists(ctx context.Context, ref string) (bool, error) {
	err := c.do(ctx, http.MethodGet, "/images/"+url.PathEscape(ref)+"/json", nil, nil, http.StatusOK)
	if IsNotFound(err) {
		return false, nil
	}
	return err == nil, err
}

// NetworkLabels returns the labels of the network named name, or a not-found error.
func (c *Client) NetworkLabels(ctx context.Context, name string) (map[string]string, error) {
	var n struct {
		Labels map[string]string `json:"Labels"`
	}
	err := c.do(ctx, http.MethodGet, "/networks/"+url.PathEscape(name), nil, &n, http.StatusOK)
	return n.Labels, err
}

// Container is one container as a labelled list returns it, with its inspected state.
type Container struct {
	ID       string            `json:"Id"`
	Names    []string          `json:"Names"`
	Labels   map[string]string `json:"Labels"`
	State    string            `json:"State"`
	Status   string            `json:"Status"`
	Health   string            `json:"-"`
	ExitCode int               `json:"-"`
}

// Containers lists every container carrying all of labels (key=value), running or not, and inspects each one
// for its health and exit code. Each one listed carries timelike's label, so inspecting it is acting on our own.
func (c *Client) Containers(ctx context.Context, labels ...string) ([]Container, error) {
	var out []Container
	if err := c.do(ctx, http.MethodGet, "/containers/json?all=1&filters="+labelFilter(labels...), nil, &out,
		http.StatusOK); err != nil {
		return nil, err
	}
	for i := range out {
		var in struct {
			State struct {
				Status   string `json:"Status"`
				ExitCode int    `json:"ExitCode"`
				Health   *struct {
					Status string `json:"Status"`
				} `json:"Health"`
			} `json:"State"`
		}
		err := c.do(ctx, http.MethodGet, "/containers/"+out[i].ID+"/json", nil, &in, http.StatusOK)
		if IsNotFound(err) {
			out[i].State = "removed"
			continue
		}
		if err != nil {
			return nil, err
		}
		out[i].State, out[i].ExitCode = in.State.Status, in.State.ExitCode
		if in.State.Health != nil {
			out[i].Health = in.State.Health.Status
		}
	}
	return out, nil
}

// Object is a network or a volume found by label.
type Object struct {
	ID     string            `json:"Id"`
	Name   string            `json:"Name"`
	Labels map[string]string `json:"Labels"`
}

// Networks lists the networks carrying all of labels.
func (c *Client) Networks(ctx context.Context, labels ...string) ([]Object, error) {
	var out []Object
	err := c.do(ctx, http.MethodGet, "/networks?filters="+labelFilter(labels...), nil, &out, http.StatusOK)
	return out, err
}

// Volumes lists the volumes carrying all of labels.
func (c *Client) Volumes(ctx context.Context, labels ...string) ([]Object, error) {
	var out struct {
		Volumes []Object `json:"Volumes"`
	}
	err := c.do(ctx, http.MethodGet, "/volumes?filters="+labelFilter(labels...), nil, &out, http.StatusOK)
	return out.Volumes, err
}

// Counts is how many of each kind of object.
type Counts struct {
	Containers int `json:"containers"`
	Networks   int `json:"networks"`
	Volumes    int `json:"volumes"`
}

// Total is the sum of the three.
func (n Counts) Total() int { return n.Containers + n.Networks + n.Volumes }

// Count reads back how many containers, networks and volumes carry env=name.
func (c *Client) Count(ctx context.Context, name string) (Counts, error) {
	l := LabelEnv + "=" + name
	var n Counts
	cs, err := c.Containers(ctx, l)
	if err != nil {
		return n, err
	}
	ns, err := c.Networks(ctx, l)
	if err != nil {
		return n, err
	}
	vs, err := c.Volumes(ctx, l)
	if err != nil {
		return n, err
	}
	return Counts{len(cs), len(ns), len(vs)}, nil
}

// Down removes everything labelled env=name: containers (stopped, then removed with their anonymous volumes),
// then networks, then volumes. It returns what it removed and what it read back as left afterwards. It never
// touches an object it did not find by the label.
func (c *Client) Down(ctx context.Context, name string) (removed, left Counts, err error) {
	l := LabelEnv + "=" + name
	cs, err := c.Containers(ctx, l)
	if err != nil {
		return removed, left, err
	}
	var errs []error
	for _, ct := range cs {
		if ct.State == "running" || ct.State == "restarting" || ct.State == "paused" {
			if e := c.do(ctx, http.MethodPost, "/containers/"+ct.ID+"/stop?t=10", nil, nil,
				http.StatusNoContent, http.StatusNotModified, http.StatusNotFound); e != nil {
				errs = append(errs, e)
			}
		}
		e := c.do(ctx, http.MethodDelete, "/containers/"+ct.ID+"?v=1&force=1", nil, nil, http.StatusNoContent,
			http.StatusNotFound)
		if e != nil {
			errs = append(errs, e)
		} else {
			removed.Containers++
		}
	}
	ns, err := c.Networks(ctx, l)
	if err != nil {
		return removed, left, err
	}
	for _, n := range ns {
		if e := c.do(ctx, http.MethodDelete, "/networks/"+n.ID, nil, nil, http.StatusNoContent, http.StatusNotFound); e != nil {
			errs = append(errs, e)
		} else {
			removed.Networks++
		}
	}
	vs, err := c.Volumes(ctx, l)
	if err != nil {
		return removed, left, err
	}
	for _, v := range vs {
		if e := c.do(ctx, http.MethodDelete, "/volumes/"+url.PathEscape(v.Name), nil, nil, http.StatusNoContent,
			http.StatusNotFound); e != nil {
			errs = append(errs, e)
		} else {
			removed.Volumes++
		}
	}
	left, err = c.Count(ctx, name)
	if err != nil {
		return removed, left, err
	}
	return removed, left, errors.Join(errs...)
}

// Sandbox is one throwaway container (014 research R2). It is created with no network, no capabilities, a
// read-only root and only the binds given, and it is always removed.
type Sandbox struct {
	Image      string
	Entrypoint []string
	Cmd        []string
	User       string
	Env        []string
	WorkingDir string
	Binds      []string // "src:dst:ro"
	Name       string
	Timeout    time.Duration
}

// Run creates, starts and waits for the sandbox, then reads its stdout and stderr and removes it.
func (c *Client) Run(ctx context.Context, s Sandbox) (stdout, stderr []byte, exit int, err error) {
	timeout := s.Timeout
	if timeout <= 0 {
		timeout = 60 * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	spec := map[string]any{
		"Image": s.Image, "Entrypoint": s.Entrypoint, "Cmd": s.Cmd, "User": s.User, "Env": s.Env,
		"WorkingDir": s.WorkingDir, "NetworkDisabled": true,
		"Labels": map[string]string{LabelSandbox: "resolve"},
		"HostConfig": map[string]any{
			"NetworkMode": "none", "Binds": s.Binds, "ReadonlyRootfs": true, "CapDrop": []string{"ALL"},
			"SecurityOpt": []string{"no-new-privileges"}, "Tmpfs": map[string]string{"/tmp": "rw,size=64m"},
			"Memory": 512 << 20, "PidsLimit": 256, "AutoRemove": false,
		},
	}
	var made struct {
		ID string `json:"Id"`
	}
	path := "/containers/create"
	if s.Name != "" {
		path += "?name=" + url.QueryEscape(s.Name)
	}
	if err := c.do(ctx, http.MethodPost, path, spec, &made, http.StatusCreated); err != nil {
		return nil, nil, 0, err
	}
	defer func() {
		rm, done := context.WithTimeout(context.Background(), 20*time.Second)
		defer done()
		_ = c.do(rm, http.MethodDelete, "/containers/"+made.ID+"?v=1&force=1", nil, nil, http.StatusNoContent,
			http.StatusNotFound)
	}()
	if err := c.do(ctx, http.MethodPost, "/containers/"+made.ID+"/start", nil, nil, http.StatusNoContent); err != nil {
		return nil, nil, 0, err
	}
	var waited struct {
		StatusCode int `json:"StatusCode"`
	}
	if err := c.do(ctx, http.MethodPost, "/containers/"+made.ID+"/wait", nil, &waited, http.StatusOK); err != nil {
		if ctx.Err() != nil {
			return nil, nil, 0, fmt.Errorf("the resolution sandbox did not finish within %s", timeout)
		}
		return nil, nil, 0, err
	}
	stdout, stderr, err = c.logs(ctx, made.ID)
	return stdout, stderr, waited.StatusCode, err
}

func (c *Client) logs(ctx context.Context, id string) ([]byte, []byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "http://docker/containers/"+id+"/logs?stdout=1&stderr=1", nil)
	if err != nil {
		return nil, nil, err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, nil, &APIError{Status: resp.StatusCode, Path: "/containers/logs", Message: "cannot read the sandbox's output"}
	}
	return Demux(io.LimitReader(resp.Body, MaxOutput))
}

// Demux splits the daemon's multiplexed log stream (8-byte frame headers: stream, 3 zero bytes, size).
func Demux(r io.Reader) (stdout, stderr []byte, err error) {
	var o, e bytes.Buffer
	hdr := make([]byte, 8)
	for {
		if _, err := io.ReadFull(r, hdr); err != nil {
			if errors.Is(err, io.EOF) {
				return o.Bytes(), e.Bytes(), nil
			}
			return o.Bytes(), e.Bytes(), fmt.Errorf("the sandbox's output stream was cut: %w", err)
		}
		n := int64(binary.BigEndian.Uint32(hdr[4:]))
		w := &o
		if hdr[0] == 2 {
			w = &e
		}
		if _, err := io.CopyN(w, r, n); err != nil {
			return o.Bytes(), e.Bytes(), fmt.Errorf("the sandbox's output stream was cut: %w", err)
		}
	}
}
