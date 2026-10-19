package engine

// Feature 13 slice 1 (014 plan § Slice 1, R14-R18): builds from a context the sandbox streams, exec in an
// environment's container, built images in down's count, the requesting agent container read from the daemon, and
// a sandbox whose stdout is attached rather than logged.
//
// The host's standing rule still holds: every image listed or removed here carries timelike's environment label,
// every container inspected was found by a timelike label, and the classic builder's own intermediate containers
// are the daemon's, removed by the build itself (forcerm).

import (
	"bufio"
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Labels slice 1 adds (014 data-model § Slice 1).
const (
	LabelSession      = LabelPrefix + "session"
	LabelGrant        = LabelPrefix + "grant"
	LabelRequester    = LabelPrefix + "requester"
	LabelOneShot      = LabelPrefix + "one-shot"
	LabelDevcontainer = LabelPrefix + "devcontainer"
	LabelRemoteUser   = LabelPrefix + "remote-user"
	LabelWorkdir      = LabelPrefix + "workdir"
	LabelRemoteEnv    = LabelPrefix + "remote-env"
	LabelBuildKey     = LabelPrefix + "build-key"
	// LabelAgent is the agent container's launch label (compose.yaml, slice 0): the one Adele finds requesters by.
	LabelAgent = LabelPrefix + "host-git"
	// RequestNetwork is the suffix of the network the agent reaches Adele on (compose.yaml's adele-request).
	RequestNetwork = "adele-request"
)

// Image is one image as a labelled list returns it.
type Image struct {
	ID       string            `json:"Id"`
	RepoTags []string          `json:"RepoTags"`
	Labels   map[string]string `json:"Labels"`
}

// Images lists the images carrying all of labels.
func (c *Client) Images(ctx context.Context, labels ...string) ([]Image, error) {
	var out []Image
	err := c.do(ctx, http.MethodGet, "/images/json?filters="+labelFilter(labels...), nil, &out, http.StatusOK)
	return out, err
}

// ImageLabels inspects an image by reference and returns its labels, and whether it exists. It never pulls.
func (c *Client) ImageLabels(ctx context.Context, ref string) (map[string]string, bool, error) {
	var in struct {
		Config struct {
			Labels map[string]string `json:"Labels"`
		} `json:"Config"`
	}
	err := c.do(ctx, http.MethodGet, "/images/"+url.PathEscape(ref)+"/json", nil, &in, http.StatusOK)
	if IsNotFound(err) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return in.Config.Labels, true, nil
}

// AgentContainer is one container carrying the agent's launch label, with its address on each network.
type AgentContainer struct {
	ID        string
	Addresses map[string]string // network name -> IPv4 address
}

// Agents lists the containers carrying the agent's launch label (R18).
func (c *Client) Agents(ctx context.Context) ([]AgentContainer, error) {
	var out []struct {
		ID              string `json:"Id"`
		NetworkSettings struct {
			Networks map[string]struct {
				IPAddress string `json:"IPAddress"`
			} `json:"Networks"`
		} `json:"NetworkSettings"`
	}
	if err := c.do(ctx, http.MethodGet, "/containers/json?all=1&filters="+labelFilter(LabelAgent), nil, &out,
		http.StatusOK); err != nil {
		return nil, err
	}
	agents := make([]AgentContainer, 0, len(out))
	for _, o := range out {
		a := AgentContainer{ID: o.ID, Addresses: map[string]string{}}
		for name, n := range o.NetworkSettings.Networks {
			a.Addresses[name] = n.IPAddress
		}
		agents = append(agents, a)
	}
	return agents, nil
}

// RequesterOf returns the id of the agent container whose address on the request network is ip, and whether one
// has it. The address is the request's peer, read by Adele's own listener: never something the client says.
func RequesterOf(agents []AgentContainer, ip string) (string, bool) {
	if ip == "" {
		return "", false
	}
	for _, a := range agents {
		for name, addr := range a.Addresses {
			if (name == RequestNetwork || strings.HasSuffix(name, "_"+RequestNetwork)) && addr == ip {
				return a.ID, true
			}
		}
	}
	return "", false
}

// LogTail returns the last n lines a labelled container wrote, stdout's then stderr's (for a one-shot that exited
// non-zero; decision C).
func (c *Client) LogTail(ctx context.Context, id string, n int) ([]string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("http://docker/containers/%s/logs?stdout=1&stderr=1&tail=%d", url.PathEscape(id), n), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cannot reach the Docker daemon at %s from Adele's container: %w", c.Socket, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, &APIError{Status: resp.StatusCode, Path: "/containers/logs", Message: "cannot read the container's output"}
	}
	o, e, err := Demux(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	var lines []string
	for _, s := range []string{string(o), string(e)} {
		for _, l := range strings.Split(strings.TrimRight(s, "\n"), "\n") {
			if l != "" {
				lines = append(lines, l)
			}
		}
	}
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return lines, nil
}

// ContainerEnv returns a labelled container's environment as the daemon has it (for remoteEnv's ${containerEnv:X}).
func (c *Client) ContainerEnv(ctx context.Context, id string) ([]string, error) {
	var in struct {
		Config struct {
			Env []string `json:"Env"`
		} `json:"Config"`
	}
	err := c.do(ctx, http.MethodGet, "/containers/"+url.PathEscape(id)+"/json", nil, &in, http.StatusOK)
	return in.Config.Env, err
}

// demuxTo copies the daemon's multiplexed stream (8-byte frame headers: stream, 3 zero bytes, size) to stdout and
// stderr as it arrives. It returns at the stream's end, or the first error from either side.
func demuxTo(r io.Reader, stdout, stderr io.Writer) error {
	br := bufio.NewReaderSize(r, 64<<10)
	hdr := make([]byte, 8)
	for {
		if _, err := io.ReadFull(br, hdr); err != nil {
			if errors.Is(err, io.EOF) {
				return nil
			}
			return fmt.Errorf("the stream was cut: %w", err)
		}
		n := int64(binary.BigEndian.Uint32(hdr[4:]))
		w := stdout
		if hdr[0] == 2 {
			w = stderr
		}
		if _, err := io.CopyN(w, br, n); err != nil {
			return err
		}
	}
}

// tail keeps the last max bytes written to it and counts what it dropped.
type tail struct {
	max     int
	buf     []byte
	dropped int64
}

func (t *tail) Write(p []byte) (int, error) {
	t.buf = append(t.buf, p...)
	if over := len(t.buf) - t.max; over > 0 {
		t.dropped += int64(over)
		t.buf = append(t.buf[:0], t.buf[over:]...)
	}
	return len(p), nil
}

// upgraded POSTs to path asking for the connection to be upgraded to a raw stream, as attach and exec start
// want, and returns the stream: the body of a 101, or of a 200 from a daemon that streams without upgrading.
func (c *Client) upgraded(ctx context.Context, path string, body any) (io.ReadCloser, error) {
	var rd io.Reader = http.NoBody
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		rd = bytes.NewReader(raw)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "http://docker"+path, rd)
	if err != nil {
		return nil, err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	req.Header.Set("Connection", "Upgrade")
	req.Header.Set("Upgrade", "tcp")
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cannot reach the Docker daemon at %s from Adele's container: %w", c.Socket, err)
	}
	if resp.StatusCode != http.StatusSwitchingProtocols && resp.StatusCode != http.StatusOK {
		defer resp.Body.Close()
		data, _ := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
		var m struct {
			Message string `json:"message"`
		}
		_ = json.Unmarshal(data, &m)
		return nil, &APIError{Status: resp.StatusCode, Message: m.Message, Path: strings.SplitN(path, "?", 2)[0]}
	}
	return resp.Body, nil
}

// RunStream is Run for a sandbox whose stdout is the product (the context archive, R14): its stdout is copied to w
// as it arrives, from an attached stream, and nothing it writes goes to the daemon's log (LogConfig none), because
// the log driver re-encodes output as JSON strings and writes it to the host's disk. stderr is kept, at most 64 KiB.
// The sandbox is removed in every case, as Run's are.
func (c *Client) RunStream(ctx context.Context, s Sandbox, w io.Writer) (stderr []byte, exit int, err error) {
	timeout := s.Timeout
	if timeout <= 0 {
		timeout = 60 * time.Second
	}
	parent := ctx
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	began, phase := time.Now(), "create"
	failed := func(e error) error {
		return &SandboxError{Phase: phase, Elapsed: time.Since(began), Bound: timeout, Err: e,
			TimedOut: errors.Is(ctx.Err(), context.DeadlineExceeded) && parent.Err() == nil}
	}
	spec := map[string]any{
		"Image": s.Image, "Entrypoint": s.Entrypoint, "Cmd": s.Cmd, "User": s.User, "Env": s.Env,
		"WorkingDir": s.WorkingDir, "NetworkDisabled": true, "AttachStdout": true, "AttachStderr": true,
		"Labels": sandboxLabels(),
		"HostConfig": map[string]any{
			"NetworkMode": "none", "Binds": s.Binds, "ReadonlyRootfs": true, "CapDrop": []string{"ALL"},
			"SecurityOpt": []string{"no-new-privileges"}, "Tmpfs": map[string]string{"/tmp": "rw,size=64m"},
			"Memory": 512 << 20, "PidsLimit": 256, "AutoRemove": false,
			"LogConfig": map[string]any{"Type": "none"},
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
		var ae *APIError
		if s.Name != "" && !errors.As(err, &ae) {
			go c.removeLate(s.Name, LateRemoval)
		}
		return nil, 0, failed(err)
	}
	defer func() {
		rm, done := context.WithTimeout(context.Background(), 20*time.Second)
		defer done()
		if err := c.remove(rm, made.ID); err != nil {
			go c.removeLate(made.ID, LateRemoval)
		}
	}()
	phase = "attach"
	stream, err := c.upgraded(ctx, "/containers/"+made.ID+"/attach?stream=1&stdout=1&stderr=1", nil)
	if err != nil {
		return nil, 0, failed(err)
	}
	defer stream.Close()
	phase = "start"
	if err := c.do(ctx, http.MethodPost, "/containers/"+made.ID+"/start", nil, nil, http.StatusNoContent); err != nil {
		return nil, 0, failed(err)
	}
	phase = "stream"
	errs := &tail{max: 64 << 10}
	if err := demuxTo(stream, w, errs); err != nil {
		return errs.buf, 0, failed(err)
	}
	phase = "wait"
	var waited struct {
		StatusCode int `json:"StatusCode"`
	}
	if err := c.do(ctx, http.MethodPost, "/containers/"+made.ID+"/wait", nil, &waited, http.StatusOK); err != nil {
		return errs.buf, 0, failed(err)
	}
	return errs.buf, waited.StatusCode, nil
}

// BuildSpec is one build for the daemon's classic builder (R15).
type BuildSpec struct {
	Tag        string
	Dockerfile string // its path inside the context archive
	Target     string
	Args       map[string]string
	Labels     map[string]string
	Timeout    time.Duration
}

// BuildError says how a build ended without an image. Kind is "step" (a step failed), "pull" (the daemon began to
// pull an image, so the build was stopped: a build pulls nothing), "timeout" (its bound passed), or "daemon".
//
// Where it ended is said in the Dockerfile's own terms (lane 13s1a). The daemon's "Step N/M" counts more than the
// agent wrote: its classic builder appends one LABEL step per label in the request to the last stage (moby's
// buildLabelOptions), so Adele's six labels made a two-instruction Dockerfile "of 8". Steps are numbered in the
// Dockerfile's order and the label steps come last, so N is the instruction's position in the Dockerfile; M is
// never printed.
type BuildError struct {
	Kind        string
	Position    int      // the instruction it was in, counted among the Dockerfile's own from 1; 0 before the first
	Instruction string   // that instruction as the Dockerfile has it
	InLabels    bool     // it was in the LABEL steps the daemon adds for the request's labels, after the Dockerfile's last
	Image       string   // for a pull: what it began to pull
	Msg         string   // the daemon's error, for a failed step
	Last        []string // the last lines of that step's own output
	Err         error
}

// Where says where the build ended, or "" before its first instruction.
func (e *BuildError) Where() string {
	switch {
	case e.InLabels:
		return "the labels Adele adds after the Dockerfile's last instruction"
	case e.Position > 0:
		return fmt.Sprintf("instruction %d of the Dockerfile, %s", e.Position, e.Instruction)
	}
	return ""
}

func (e *BuildError) Error() string {
	at := ""
	if w := e.Where(); w != "" {
		at = " at " + w
	}
	switch e.Kind {
	case "pull":
		return fmt.Sprintf("the daemon began to pull %s%s, so the build was stopped: a build pulls nothing", e.Image, at)
	case "timeout":
		return "the build did not finish within its bound" + at
	case "step":
		return "the build failed" + at + ": " + e.Msg
	}
	return fmt.Sprintf("the build failed%s: %v", at, e.Err)
}

func (e *BuildError) Unwrap() error { return e.Err }

// pullStatus reports whether a build progress status is the daemon pulling an image.
func pullStatus(s string) bool {
	for _, p := range []string{"Pulling", "Downloading", "Download complete", "Pull complete", "Extracting",
		"Verifying Checksum", "Digest: ", "Status: Downloaded", "Waiting"} {
		if strings.HasPrefix(s, p) {
			return true
		}
	}
	return false
}

// Build streams archive (the context tar, which Adele never opens) to the daemon's classic builder and reads its progress.
// Two things make a build pull nothing (R15): the caller has checked every base image is on the daemon, and here
// the first progress message that is a pull cancels the request, which stops the build. It returns the image id.
func (c *Client) Build(ctx context.Context, b BuildSpec, archive io.Reader) (string, error) {
	timeout := b.Timeout
	if timeout <= 0 {
		timeout = 5 * time.Minute
	}
	parent := ctx
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	q := url.Values{}
	q.Set("t", b.Tag)
	q.Set("dockerfile", b.Dockerfile)
	if b.Target != "" {
		q.Set("target", b.Target)
	}
	args, _ := json.Marshal(nonNil(b.Args))
	labels, _ := json.Marshal(nonNil(b.Labels))
	q.Set("buildargs", string(args))
	q.Set("labels", string(labels))
	for k, v := range map[string]string{"pull": "0", "rm": "1", "forcerm": "1", "networkmode": "default",
		"version": "1", "q": "0"} {
		q.Set(k, v)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "http://docker/build?"+q.Encode(), archive)
	if err != nil {
		return "", &BuildError{Kind: "daemon", Err: err}
	}
	req.Header.Set("Content-Type", "application/x-tar")
	var at BuildError // where the build is: Position, Instruction, InLabels
	var last []string
	keep := func(s string) {
		for _, l := range strings.Split(strings.TrimRight(s, "\n"), "\n") {
			if l = strings.TrimSpace(l); l == "" || strings.HasPrefix(l, "--->") || strings.HasPrefix(l, "Removing intermediate container") {
				continue // the daemon's own bookkeeping between steps, not the step's output
			}
			last = append(last, l)
			if len(last) > 6 {
				last = last[1:]
			}
		}
	}
	ended := func(e error) error {
		if errors.Is(ctx.Err(), context.DeadlineExceeded) && parent.Err() == nil {
			return &BuildError{Kind: "timeout", Position: at.Position, Instruction: at.Instruction, InLabels: at.InLabels, Last: last, Err: e}
		}
		return &BuildError{Kind: "daemon", Position: at.Position, Instruction: at.Instruction, InLabels: at.InLabels, Last: last, Err: e}
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return "", ended(fmt.Errorf("cannot reach the Docker daemon at %s from Adele's container: %w", c.Socket, err))
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		data, _ := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
		var m struct {
			Message string `json:"message"`
		}
		_ = json.Unmarshal(data, &m)
		return "", ended(&APIError{Status: resp.StatusCode, Message: m.Message, Path: "/build"})
	}
	dec := json.NewDecoder(io.LimitReader(resp.Body, 64<<20))
	var id string
	for {
		var msg struct {
			Stream      string `json:"stream"`
			Status      string `json:"status"`
			ID          string `json:"id"`
			Error       string `json:"error"`
			ErrorDetail struct {
				Message string `json:"message"`
			} `json:"errorDetail"`
			Aux struct {
				ID string `json:"ID"`
			} `json:"aux"`
		}
		if err := dec.Decode(&msg); err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			return "", ended(err)
		}
		switch {
		case msg.Error != "":
			text := msg.ErrorDetail.Message
			if text == "" {
				text = msg.Error
			}
			return "", &BuildError{Kind: "step", Position: at.Position, Instruction: at.Instruction, InLabels: at.InLabels,
				Msg: strings.TrimSpace(text), Last: last}
		case pullStatus(msg.Status):
			image := msg.ID
			if i := strings.Index(msg.Status, "Pulling from "); i >= 0 {
				image = strings.TrimSpace(msg.Status[i+len("Pulling from "):])
			}
			cancel()
			return "", &BuildError{Kind: "pull", Position: at.Position, Instruction: at.Instruction, InLabels: at.InLabels,
				Image: image, Last: last}
		case msg.Aux.ID != "":
			id = msg.Aux.ID
		case msg.Stream != "":
			if n, text, ok := stepLine(msg.Stream); ok {
				at = BuildError{Position: n, Instruction: text, InLabels: labelStep(text, b.Labels)}
				last = nil // the lines kept are this step's own
				continue
			}
			keep(msg.Stream)
			if s := strings.TrimSpace(msg.Stream); strings.HasPrefix(s, "Successfully built ") && id == "" {
				id = strings.TrimPrefix(s, "Successfully built ")
			}
		}
	}
	if ctx.Err() != nil {
		return "", ended(ctx.Err())
	}
	if id == "" {
		return "", &BuildError{Kind: "step", Position: at.Position, Instruction: at.Instruction, InLabels: at.InLabels,
			Msg: "the daemon reported no image", Last: last}
	}
	return id, nil
}

var stepRe = regexp.MustCompile(`(?s)^Step ([0-9]+)/[0-9]+ : (.*)$`)

// stepLine reads the classic builder's "Step N/M : <instruction>" header, which it writes as one message. The
// instruction is the Dockerfile's text; a continued one is put on one line.
func stepLine(stream string) (int, string, bool) {
	m := stepRe.FindStringSubmatch(strings.TrimSpace(stream))
	if m == nil {
		return 0, "", false
	}
	n, err := strconv.Atoi(m[1])
	if err != nil {
		return 0, "", false
	}
	return n, strings.Join(strings.Fields(m[2]), " "), true
}

// labelStep reports whether a step's instruction is one of the LABEL steps the daemon adds for labels, one per
// label, as "LABEL <key>=<value>".
func labelStep(text string, labels map[string]string) bool {
	for k := range labels {
		if strings.HasPrefix(text, "LABEL "+k+"=") {
			return true
		}
	}
	return false
}

func nonNil(m map[string]string) map[string]string {
	if m == nil {
		return map[string]string{}
	}
	return m
}

// ExecSpec is one command run in a container (R13, R17). It is never privileged and has no TTY.
type ExecSpec struct {
	Cmd        []string
	User       string
	WorkingDir string
	Env        []string
	Timeout    time.Duration
	MaxOutput  int // bytes kept of each of stdout and stderr, the last ones
}

// ExecResult is how it ended. TimedOut means its bound passed: the Engine API has no call that stops an exec'd
// process, so it may still be running in the container.
type ExecResult struct {
	ExitCode int
	Stdout   []byte
	Stderr   []byte
	Dropped  [2]int64 // bytes of stdout and stderr not kept
	TimedOut bool
	Took     time.Duration
}

// Exec runs spec in the container id, attached, and returns its exit code and the last of its output.
func (c *Client) Exec(ctx context.Context, id string, spec ExecSpec) (ExecResult, error) {
	timeout, max := spec.Timeout, spec.MaxOutput
	if timeout <= 0 {
		timeout = 100 * time.Second
	}
	if max <= 0 {
		max = 1 << 20
	}
	began := time.Now()
	var made struct {
		ID string `json:"Id"`
	}
	env := spec.Env
	if env == nil {
		env = []string{}
	}
	if err := c.do(ctx, http.MethodPost, "/containers/"+url.PathEscape(id)+"/exec", map[string]any{
		"AttachStdin": false, "AttachStdout": true, "AttachStderr": true, "Tty": false, "Privileged": false,
		"Cmd": spec.Cmd, "User": spec.User, "WorkingDir": spec.WorkingDir, "Env": env,
	}, &made, http.StatusCreated); err != nil {
		return ExecResult{}, err
	}
	run, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	out, errs := &tail{max: max}, &tail{max: max}
	res := ExecResult{}
	stream, err := c.upgraded(run, "/exec/"+made.ID+"/start", map[string]any{"Detach": false, "Tty": false})
	if err == nil {
		err = demuxTo(stream, out, errs)
		stream.Close()
	}
	res.Stdout, res.Stderr, res.Dropped = out.buf, errs.buf, [2]int64{out.dropped, errs.dropped}
	res.Took = time.Since(began)
	if errors.Is(run.Err(), context.DeadlineExceeded) && ctx.Err() == nil {
		res.TimedOut = true
		return res, nil
	}
	if err != nil {
		return res, err
	}
	var in struct {
		ExitCode int  `json:"ExitCode"`
		Running  bool `json:"Running"`
	}
	if err := c.do(ctx, http.MethodGet, "/exec/"+made.ID+"/json", nil, &in, http.StatusOK); err != nil {
		return res, err
	}
	res.ExitCode = in.ExitCode
	return res, nil
}

// RemoveImage removes an image a request just built and is not keeping (a refusal after the build, or an archive
// that was not the one resolve keyed). One already gone is removed.
func (c *Client) RemoveImage(ctx context.Context, ref string) error {
	return c.do(ctx, http.MethodDelete, "/images/"+url.PathEscape(ref)+"?force=1", nil, nil, http.StatusOK, http.StatusNotFound)
}
