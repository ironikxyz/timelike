// Package compose is what Adele knows of a compose project's resolved model (feature 13, slice 0; 014 research
// R2-R5): its name, the settings she refuses, the bind sources to resolve in the sandbox, the images it needs, the
// ports it publishes, and the labels and network she adds before running it.
//
// It reads only the model `docker-compose config --format json` printed in the sandbox: the project after
// interpolation, include, extends, profiles and override files. Never the text the agent wrote (cross-stack P002,
// P004).
package compose

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"timelike/adele/internal/engine"
)

// Network is the shared internal network the agent and every nested service join (014 research R8).
const Network = "timelike-nested"

// Model is a resolved compose model, as JSON decodes it.
type Model = map[string]any

var nameRe = regexp.MustCompile(`^tl-[a-z0-9][a-z0-9-]{0,59}$`)

// ValidName reports whether name is an environment name Adele accepts.
func ValidName(name string) bool { return nameRe.MatchString(name) }

var slugRe = regexp.MustCompile(`[^a-z0-9]+`)

// DefaultName is the environment name for a project directory: tl-<basename slug, at most 40>-<sha256(dir)[:6]>,
// unique per directory (spec FR-2).
func DefaultName(dir string) string {
	slug := strings.Trim(slugRe.ReplaceAllString(strings.ToLower(filepath.Base(dir)), "-"), "-")
	if len(slug) > 40 {
		slug = strings.Trim(slug[:40], "-")
	}
	if slug == "" {
		slug = "project"
	}
	sum := sha256.Sum256([]byte(filepath.Clean(dir)))
	return "tl-" + slug + "-" + hex.EncodeToString(sum[:])[:6]
}

// Within reports whether path is ws or lies under it, lexically.
func Within(path, ws string) bool {
	if path == "" || ws == "" || !filepath.IsAbs(path) {
		return false
	}
	p, w := filepath.Clean(path), filepath.Clean(ws)
	return p == w || strings.HasPrefix(p, w+"/")
}

// Refusal is one thing Adele will not run, named for the agent. Kind is "setting" (no grant allows it, revision
// 17), "file" (a file outside the workspace, which the sandbox cannot see; also no grant allows it) or "image" (a
// missing image; the operator's docker pull, FOR-MENTOR Item 29).
type Refusal struct {
	Kind    string `json:"refusal"`
	Service string `json:"service,omitempty"`
	Setting string `json:"setting"`
	Value   string `json:"value"`
	Remedy  string `json:"remediation"`
}

// NoGrant reports whether no grant can allow the refusal: every kind but a missing image.
func (r *Refusal) NoGrant() bool { return r.Kind != KindImage }

// Refusal kinds.
const (
	KindSetting = "setting"
	KindFile    = "file"
	KindImage   = "image"
)

func refuse(svc, setting string, value any, remedy string) *Refusal {
	return &Refusal{Kind: KindSetting, Service: svc, Setting: setting, Value: short(value), Remedy: remedy}
}

func short(v any) string {
	var s string
	switch t := v.(type) {
	case string:
		s = t
	case nil:
		s = ""
	default:
		raw, _ := json.Marshal(t)
		s = string(raw)
	}
	if len(s) > 120 {
		s = s[:117] + "..."
	}
	return s
}

var topLevel = map[string]bool{"name": true, "services": true, "networks": true, "volumes": true, "secrets": true,
	"configs": true}

// hostOnly are the namespace settings refused when set to host (or, for pid and ipc, to another container).
var hostOnly = []string{"pid", "ipc", "uts", "userns_mode", "cgroup"}

// forbidden are service keys refused whenever they are present and not empty.
var forbidden = []struct{ key, remedy string }{
	{"cap_add", "drop cap_add: no added capability is brokered"},
	{"devices", "drop devices: no host device is brokered"},
	{"device_cgroup_rules", "drop device_cgroup_rules"},
	{"gpus", "drop gpus: no host device is brokered"},
	{"runtime", "drop runtime: only the daemon's default runtime is brokered"},
	{"cgroup_parent", "drop cgroup_parent"},
	{"external_links", "drop external_links: link to services of this project instead"},
	{"container_name", "drop container_name: Adele names containers within the project"},
}

// buildAllowed are the build keys slice 1 brokers (014 research R16). The others are refused by name: no grant
// allows build secrets, SSH forwarding, another build network, entitlements, privileged builds or additional
// contexts (the operator's decision 1), and the rest are not brokered.
var buildAllowed = map[string]bool{"context": true, "dockerfile": true, "args": true, "target": true, "labels": true}

var buildRefused = map[string]struct{ setting, remedy string }{
	"secrets":             {"build secrets", "drop build.secrets: no grant allows a build secret"},
	"ssh":                 {"build ssh", "drop build.ssh: no grant allows SSH forwarding into a build"},
	"entitlements":        {"build entitlements", "drop build.entitlements: no grant allows them"},
	"privileged":          {"build privileged", "drop build.privileged: no grant allows a privileged build"},
	"additional_contexts": {"build additional_contexts", "drop build.additional_contexts: a build gets its one context"},
}

func checkBuild(name string, b map[string]any, ws string) *Refusal {
	for _, k := range sortedKeys(b) {
		if !present(b[k]) {
			continue
		}
		if k == "network" {
			if v := str(b[k]); v != "default" {
				return refuse(name, "build network", v, "drop build.network: a build's RUN steps have the default network")
			}
			continue
		}
		if r, ok := buildRefused[k]; ok {
			return refuse(name, r.setting, b[k], r.remedy)
		}
		if !buildAllowed[k] {
			return refuse(name, "build."+k, b[k], "drop build."+k+": a build brokers context, dockerfile, args, target and labels")
		}
	}
	if c := str(b["context"]); !Within(c, ws) {
		return &Refusal{Kind: KindSetting, Service: name, Setting: "build.context", Value: c,
			Remedy: "use a context inside the workspace (" + ws + ")"}
	}
	return ownLabels(name, "build.labels", m(b["labels"]))
}

func m(v any) map[string]any {
	if x, ok := v.(map[string]any); ok {
		return x
	}
	return nil
}

func list(v any) []any {
	if x, ok := v.([]any); ok {
		return x
	}
	return nil
}

func str(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func present(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != ""
	case []any:
		return len(t) > 0
	case map[string]any:
		return len(t) > 0
	}
	return true
}

func sortedKeys(x map[string]any) []string {
	out := make([]string, 0, len(x))
	for k := range x {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// Services returns the service names in order.
func Services(model Model) []string { return sortedKeys(m(model["services"])) }

// Check applies the refusal list (014 research R3) to the resolved model. ws is the workspace; real maps each
// bind source BindSources returned to its resolved path in the sandbox, "" when it did not resolve. It returns
// the first refusal, in service order, or nil.
func Check(model Model, ws string, real map[string]string) *Refusal {
	for _, k := range sortedKeys(model) {
		if !topLevel[k] && !strings.HasPrefix(k, "x-") {
			return refuse("", k, k, "drop the top-level "+k+": Adele brokers services, networks, volumes, secrets and configs")
		}
	}
	services := m(model["services"])
	if len(services) == 0 {
		return refuse("", "services", "none", "the project defines no service to bring up")
	}
	for _, name := range sortedKeys(services) {
		if r := checkService(name, m(services[name]), ws, real); r != nil {
			return r
		}
	}
	for _, name := range sortedKeys(m(model["networks"])) {
		n := m(m(model["networks"])[name])
		switch {
		case present(n["external"]):
			return refuse("", "networks", name+": external", "drop external: a network outside the project is not Adele's to join")
		case str(n["driver"]) != "" && str(n["driver"]) != "bridge":
			return refuse("", "networks", name+": driver "+str(n["driver"]), "use the default bridge driver")
		case present(n["driver_opts"]):
			return refuse("", "networks", name+": driver_opts", "drop driver_opts")
		}
		if r := ownLabels("", "networks", m(n["labels"])); r != nil {
			return r
		}
	}
	for _, name := range sortedKeys(m(model["volumes"])) {
		v := m(m(model["volumes"])[name])
		switch {
		case present(v["external"]):
			return refuse("", "volumes", name+": external", "drop external: a volume outside the project is not Adele's to mount")
		case str(v["driver"]) != "" && str(v["driver"]) != "local":
			return refuse("", "volumes", name+": driver "+str(v["driver"]), "use the local driver")
		case present(v["driver_opts"]):
			return refuse("", "volumes", name+": driver_opts", "drop driver_opts: a volume may not bind a host path")
		}
		if r := ownLabels("", "volumes", m(v["labels"])); r != nil {
			return r
		}
	}
	for _, kind := range []string{"secrets", "configs"} {
		for _, name := range sortedKeys(m(model[kind])) {
			s := m(m(model[kind])[name])
			if present(s["external"]) {
				return refuse("", kind, name+": external", "drop external")
			}
			if f := str(s["file"]); f != "" {
				if r := checkPath("", kind, name+": "+f, f, ws, real); r != nil {
					return r
				}
			}
		}
	}
	return nil
}

func checkService(name string, s map[string]any, ws string, real map[string]string) *Refusal {
	if present(s["privileged"]) {
		return refuse(name, "privileged", "true", "run it without privileged")
	}
	if nm := str(s["network_mode"]); nm != "" && nm != "none" && nm != "bridge" && !strings.HasPrefix(nm, "service:") {
		return refuse(name, "network_mode", nm, "drop network_mode: the service joins the project's networks")
	}
	for _, k := range hostOnly {
		v := str(s[k])
		if v == "host" || ((k == "pid" || k == "ipc") && strings.HasPrefix(v, "container:")) {
			return refuse(name, k, v, "drop "+k+": the host's namespaces are not brokered")
		}
	}
	for _, f := range forbidden {
		if present(s[f.key]) {
			return refuse(name, f.key, s[f.key], f.remedy)
		}
	}
	for _, so := range list(s["security_opt"]) {
		if v := str(so); v != "no-new-privileges" && v != "no-new-privileges:true" && v != "no-new-privileges=true" {
			return refuse(name, "security_opt", v, "drop it: only no-new-privileges is brokered")
		}
	}
	for _, vf := range list(s["volumes_from"]) {
		if v := str(vf); strings.HasPrefix(v, "container:") {
			return refuse(name, "volumes_from", v, "take volumes from a service of this project instead")
		}
	}
	if d := m(m(m(m(s["deploy"])["resources"])["reservations"])); present(d["devices"]) {
		return refuse(name, "deploy.resources.reservations.devices", d["devices"], "drop the device reservation")
	}
	if r := ownLabels(name, "labels", m(s["labels"])); r != nil {
		return r
	}
	if b := m(s["build"]); b != nil {
		if r := checkBuild(name, b, ws); r != nil {
			return r
		}
	}
	for _, raw := range list(s["volumes"]) {
		v := m(raw)
		typ, src, dst := str(v["type"]), str(v["source"]), str(v["target"])
		switch typ {
		case "volume", "tmpfs", "":
		case "bind":
			if r := checkPath(name, "volumes", src+":"+dst, src, ws, real); r != nil {
				return r
			}
		default:
			return refuse(name, "volumes", typ+" "+src+":"+dst, "use a bind mount inside the workspace, a named volume or a tmpfs")
		}
	}
	if str(s["image"]) == "" && m(s["build"]) == nil {
		return refuse(name, "image", "none", "give the service an image that is on the daemon, or a build")
	}
	return nil
}

func ownLabels(svc, setting string, labels map[string]any) *Refusal {
	for k := range labels {
		if strings.HasPrefix(k, engine.LabelPrefix) {
			return refuse(svc, setting, k, "drop "+k+": labels under "+engine.LabelPrefix+" are Adele's own")
		}
	}
	return nil
}

func checkPath(svc, setting, value, src, ws string, real map[string]string) *Refusal {
	remedy := "use a path inside the workspace (" + ws + ")"
	if !Within(src, ws) {
		return &Refusal{Kind: KindSetting, Service: svc, Setting: setting, Value: value, Remedy: remedy}
	}
	r, ok := real[src]
	if !ok || r == "" {
		return &Refusal{Kind: KindSetting, Service: svc, Setting: setting, Value: value + " (does not resolve in the workspace)",
			Remedy: remedy + ", one that exists and is not a link out of it"}
	}
	if !Within(r, ws) {
		return &Refusal{Kind: KindSetting, Service: svc, Setting: setting, Value: value + " (resolves to " + r + ")", Remedy: remedy}
	}
	return nil
}

// BindSources returns every host path the model asks the daemon to mount: bind sources and file-backed secrets
// and configs. The sandbox resolves each one (014 research R2).
func BindSources(model Model) []string {
	seen := map[string]bool{}
	var out []string
	add := func(p string) {
		if p != "" && !seen[p] {
			seen[p] = true
			out = append(out, p)
		}
	}
	services := m(model["services"])
	for _, name := range sortedKeys(services) {
		for _, raw := range list(m(services[name])["volumes"]) {
			if v := m(raw); str(v["type"]) == "bind" {
				add(str(v["source"]))
			}
		}
	}
	for _, kind := range []string{"secrets", "configs"} {
		for _, name := range sortedKeys(m(model[kind])) {
			add(str(m(m(model[kind])[name])["file"]))
		}
	}
	return out
}

// Build is one service's build as the resolved model has it (slice 1; 014 research R14-R16). Context and Dockerfile
// are absolute: compose's config makes the context absolute, and a relative Dockerfile is relative to it.
type Build struct {
	Service    string
	Context    string
	Dockerfile string
	Args       map[string]string
	Target     string
}

// Builds returns each service's build, in service order.
func Builds(model Model) []Build {
	var out []Build
	services := m(model["services"])
	for _, name := range sortedKeys(services) {
		b := m(m(services[name])["build"])
		if b == nil {
			continue
		}
		ctx := str(b["context"])
		df := str(b["dockerfile"])
		if df == "" {
			df = "Dockerfile"
		}
		if !filepath.IsAbs(df) {
			df = filepath.Join(ctx, df)
		}
		args := map[string]string{}
		switch a := b["args"].(type) {
		case map[string]any:
			for k, v := range a {
				if s, ok := v.(string); ok {
					args[k] = s
				}
			}
		case []any:
			for _, raw := range a {
				if k, v, ok := strings.Cut(str(raw), "="); ok {
					args[k] = v
				}
			}
		}
		out = append(out, Build{Service: name, Context: ctx, Dockerfile: df, Args: args, Target: str(b["target"])})
	}
	return out
}

// WithBuildKeys returns a copy of model whose built services carry their build key, so that the model's hash
// changes when a context or Dockerfile does (D-12, cross-stack P003). The copy is for hashing only.
func WithBuildKeys(model Model, keys map[string]string) Model {
	if len(keys) == 0 {
		return model
	}
	var out Model
	raw, _ := json.Marshal(model)
	_ = json.Unmarshal(raw, &out)
	services := m(out["services"])
	for svc, key := range keys {
		if s := m(services[svc]); s != nil {
			s["x-timelike-build-key"] = key
		}
	}
	return out
}

// OneShots returns the services another service depends on with condition service_completed_successfully: one-shots
// for certain, whose exit up waits for (decision C, R20).
func OneShots(model Model) map[string]bool {
	out := map[string]bool{}
	services := m(model["services"])
	for _, name := range sortedKeys(services) {
		for dep, raw := range m(m(services[name])["depends_on"]) {
			if str(m(raw)["condition"]) == "service_completed_successfully" {
				out[dep] = true
			}
		}
	}
	return out
}

// Images maps each service to its image.
func Images(model Model) map[string]string {
	out := map[string]string{}
	services := m(model["services"])
	for name, raw := range services {
		out[name] = str(m(raw)["image"])
	}
	return out
}

func portNumber(v any) (int, bool) {
	switch t := v.(type) {
	case float64:
		return int(t), t > 0
	case string:
		s := strings.SplitN(t, "/", 2)[0]
		if i := strings.LastIndex(s, "-"); i >= 0 { // a range: its first port
			s = s[:i]
		}
		n, err := strconv.Atoi(s)
		return n, err == nil && n > 0
	}
	return 0, false
}

// Published returns the host ports the model publishes, checked against the grant's ports (D-4).
func Published(model Model) []int {
	var out []int
	services := m(model["services"])
	for _, name := range sortedKeys(services) {
		for _, raw := range list(m(services[name])["ports"]) {
			if p, ok := portNumber(m(raw)["published"]); ok {
				out = append(out, p)
			}
		}
	}
	return out
}

// ContainerPorts returns each service's container ports the agent is told about: its expose list and its ports'
// targets, sorted, without repeats.
func ContainerPorts(model Model) map[string][]int {
	out := map[string][]int{}
	services := m(model["services"])
	for name, raw := range services {
		s := m(raw)
		seen := map[int]bool{}
		for _, e := range list(s["expose"]) {
			if p, ok := portNumber(e); ok {
				seen[p] = true
			}
		}
		for _, pr := range list(s["ports"]) {
			if p, ok := portNumber(m(pr)["target"]); ok {
				seen[p] = true
			}
		}
		ports := make([]int, 0, len(seen))
		for p := range seen {
			ports = append(ports, p)
		}
		sort.Ints(ports)
		out[name] = ports
	}
	return out
}

// Hash is the SHA-256 of the checked model, in JSON's canonical (sorted) key order.
func Hash(model Model) string {
	raw, _ := json.Marshal(model)
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// Alias is the name a service answers to on the shared network.
func Alias(service, name string) string { return service + "." + name }

// Meta is what slice 1 adds to an environment's labels (014 research R13, R18, R20, R21): who asked, under which
// grant, the images its builds made, and a devcontainer's primary service and what exec needs of it.
type Meta struct {
	Session                        string
	Grant                          string
	Requester                      string            // the agent container's id, or "unknown"
	Images                         map[string]string // a built service's image tag, which replaces its build
	Primary                        string            // a devcontainer's own service, or ""
	RemoteUser, Workdir, RemoteEnv string            // the primary's exec settings; RemoteEnv is JSON
}

// Inject returns the bytes Adele runs: the checked model named name, with timelike's labels on every service,
// network and volume, every service joined to the shared network under its alias, and env_file and pull_policy
// removed (the environment is already resolved; nothing is pulled). A built service runs the image its build made.
// model is not modified.
func Inject(model Model, name string, created time.Time, ttl time.Duration, hash string, meta Meta) ([]byte, error) {
	var out Model
	raw, err := json.Marshal(model)
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	out["name"] = name
	ports := ContainerPorts(model)
	oneShots := OneShots(model)
	owned := func(labels map[string]any) {
		labels[engine.LabelEnv] = name
		labels[engine.LabelSession] = meta.Session
		labels[engine.LabelGrant] = meta.Grant
		labels[engine.LabelRequester] = meta.Requester
	}
	services := m(out["services"])
	usesDefault := false
	for _, svc := range sortedKeys(services) {
		s := m(services[svc])
		delete(s, "env_file")
		delete(s, "pull_policy")
		if img, ok := meta.Images[svc]; ok {
			delete(s, "build")
			s["image"] = img
		}
		labels := m(s["labels"])
		if labels == nil {
			labels = map[string]any{}
		}
		ps := make([]string, 0, len(ports[svc]))
		for _, p := range ports[svc] {
			ps = append(ps, strconv.Itoa(p))
		}
		owned(labels)
		labels[engine.LabelCreated] = created.UTC().Format(time.RFC3339)
		labels[engine.LabelTTL] = strconv.FormatInt(int64(ttl/time.Second), 10)
		labels[engine.LabelModel] = hash
		labels[engine.LabelPorts] = strings.Join(ps, ",")
		if oneShots[svc] {
			labels[engine.LabelOneShot] = "1"
		}
		if svc == meta.Primary && meta.Primary != "" {
			// compose interpolates the bytes it is given once more, so a value of Adele's own that holds a $ (remoteEnv's
			// ${containerEnv:X}, kept for exec) is escaped as $$, which compose reads back as $ (lane-free finding,
			// slice 1: compose up refused the label as an invalid interpolation).
			labels[engine.LabelDevcontainer] = "1"
			labels[engine.LabelRemoteUser] = escapeDollar(meta.RemoteUser)
			labels[engine.LabelWorkdir] = escapeDollar(meta.Workdir)
			labels[engine.LabelRemoteEnv] = escapeDollar(meta.RemoteEnv)
		}
		s["labels"] = labels
		if str(s["network_mode"]) != "" {
			continue // none or service:X; compose refuses networks beside network_mode
		}
		nets := m(s["networks"])
		if nets == nil {
			nets = map[string]any{"default": nil}
		}
		if _, ok := nets["default"]; ok {
			usesDefault = true
		}
		nets[Network] = map[string]any{"aliases": []any{Alias(svc, name)}}
		s["networks"] = nets
	}
	nets := m(out["networks"])
	if nets == nil {
		nets = map[string]any{}
	}
	if _, ok := nets["default"]; usesDefault && !ok {
		nets["default"] = map[string]any{"name": name + "_default"}
	}
	for k, raw := range nets {
		n := m(raw)
		if n == nil {
			n = map[string]any{}
		}
		labels := m(n["labels"])
		if labels == nil {
			labels = map[string]any{}
		}
		owned(labels)
		n["labels"] = labels
		nets[k] = n
	}
	nets[Network] = map[string]any{"external": true, "name": Network}
	out["networks"] = nets
	for k, raw := range m(out["volumes"]) {
		v := m(raw)
		if v == nil {
			v = map[string]any{}
		}
		labels := m(v["labels"])
		if labels == nil {
			labels = map[string]any{}
		}
		owned(labels)
		v["labels"] = labels
		m(out["volumes"])[k] = v
	}
	return json.Marshal(out)
}

// Resolved is what `adeled resolve` prints from the sandbox: the model, each bind source's resolved path ("" when
// it did not resolve), the variables compose said were unset, and either compose's error or a refusal made of it.
//
// Slice 1 adds a devcontainer's own settings (Dev) and, for each build, what the sandbox found (Builds, R14-R16).
type Resolved struct {
	OK      bool              `json:"ok"`
	Model   json.RawMessage   `json:"model,omitempty"`
	Real    map[string]string `json:"real,omitempty"`
	Unset   []string          `json:"unset,omitempty"`
	Error   string            `json:"error,omitempty"`
	Refusal *Refusal          `json:"refusal,omitempty"`
	Dev     *Dev              `json:"devcontainer,omitempty"`
	Builds  []BuildScan       `json:"builds,omitempty"`
}

// Dev is a devcontainer's primary service and what exec and its lifecycle commands need (014 research R12, R13).
type Dev struct {
	Primary         string            `json:"primary"`
	RemoteUser      string            `json:"remote_user"`
	RemoteEnv       map[string]string `json:"remote_env"`
	WorkspaceFolder string            `json:"workspace_folder"`
	Lifecycle       []Command         `json:"lifecycle"`
	NotRun          []string          `json:"not_run,omitempty"`
}

// Command is one lifecycle command: Shell runs with /bin/sh -c, Argv as is.
type Command struct {
	Name  string   `json:"name"`
	Shell string   `json:"shell,omitempty"`
	Argv  []string `json:"argv,omitempty"`
}

// BuildScan is one build as the sandbox found it: the real context and Dockerfile, the Dockerfile's name inside the
// archive, the context's digest, the build's key, and every base image it names (R14-R16).
type BuildScan struct {
	Service        string            `json:"service"`
	Context        string            `json:"context"`
	Dockerfile     string            `json:"dockerfile"`
	DockerfileName string            `json:"dockerfile_name"`
	Digest         string            `json:"digest"`
	Key            string            `json:"key"`
	Bases          []string          `json:"bases"`
	Args           map[string]string `json:"args"`
	Target         string            `json:"target,omitempty"`
}

var unsetRe = regexp.MustCompile(`The \\?"([A-Za-z_][A-Za-z0-9_]*)\\?" variable is not set`)

// Unset reads compose's "variable is not set" warnings.
func Unset(stderr string) []string {
	seen := map[string]bool{}
	var out []string
	for _, mm := range unsetRe.FindAllStringSubmatch(stderr, -1) {
		if !seen[mm[1]] {
			seen[mm[1]] = true
			out = append(out, mm[1])
		}
	}
	return out
}

var pathRe = regexp.MustCompile(`/[^\s"'\x60,;:()\[\]]+`)

// Outside turns compose's failure on a file it could not see into a refusal (014 research R2): the first absolute
// path in msg outside the workspace, with the setting msg's words name. nil when msg names no such path, so the
// error is the project's own.
func Outside(msg, ws string) *Refusal {
	for _, p := range pathRe.FindAllString(msg, -1) {
		p = strings.TrimRight(p, ".")
		if Within(p, ws) || p == "/" {
			continue
		}
		low := strings.ToLower(msg)
		setting := "a file"
		switch {
		case strings.Contains(low, "env file") || strings.Contains(low, "env_file"):
			setting = "env_file"
		case strings.Contains(low, "include"):
			setting = "include"
		case strings.Contains(low, "extends"):
			setting = "extends"
		}
		return &Refusal{Kind: KindFile, Setting: setting, Value: p,
			Remedy: fmt.Sprintf("keep it inside the workspace (%s): the resolution sandbox sees nothing else", ws)}
	}
	return nil
}

// escapeDollar escapes $ for compose's interpolation of the bytes Adele runs.
func escapeDollar(s string) string { return strings.ReplaceAll(s, "$", "$$") }
