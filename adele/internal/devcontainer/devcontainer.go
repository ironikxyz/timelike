// Package devcontainer translates a project's devcontainer.json into a compose project (feature 13, slice 1; 014
// research R12, R13). It runs in the resolution sandbox: it parses the file as JSONC, substitutes the variables it
// may substitute, refuses what no grant allows, and writes a compose file the sandbox then runs `compose config`
// on. So the model Adele checks is normalised and refused exactly as a compose project's is (FR-17): this package
// refuses only what compose cannot express or what would reach the host, and maps privileged, capAdd, securityOpt
// and the runArgs onto the compose keys slice 0's check already refuses.
//
// It never reads the agent's environment: ${localEnv:X} is its default, or empty, with X reported as unset.
package devcontainer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"timelike/adele/internal/compose"
)

// PrimaryService is the service an image or build devcontainer becomes.
const PrimaryService = "devcontainer"

// keepAlive is the entrypoint overrideCommand puts on the primary service: a shell loop that ends on SIGTERM, so
// the container stays up for exec and stops promptly on down.
var keepAlive = []any{"/bin/sh", "-c", "trap 'exit 0' TERM; while sleep 1000 & wait $!; do :; done"}

// lifecycleKeys are the lifecycle commands Adele runs, in the order she runs them (R13).
var lifecycleKeys = []string{"onCreateCommand", "updateContentCommand", "postCreateCommand", "postStartCommand"}

// translated are the keys this package maps; ignored are listed keys that need nothing.
var (
	translated = map[string]bool{"image": true, "build": true, "dockerComposeFile": true, "service": true,
		"runServices": true, "containerEnv": true, "remoteEnv": true, "containerUser": true, "remoteUser": true,
		"workspaceFolder": true, "workspaceMount": true, "mounts": true, "forwardPorts": true, "overrideCommand": true,
		"runArgs": true, "privileged": true, "capAdd": true, "securityOpt": true, "init": true,
		"onCreateCommand": true, "updateContentCommand": true, "postCreateCommand": true, "postStartCommand": true}
	ignored = map[string]bool{"name": true, "customizations": true, "hostRequirements": true, "portsAttributes": true,
		"otherPortsAttributes": true, "shutdownAction": true, "waitFor": true, "userEnvProbe": true,
		"updateRemoteUserUID": true, "$schema": true}
)

// Find returns the devcontainer.json for the project folder dir: dir/.devcontainer/devcontainer.json, else
// dir/.devcontainer.json. A directory of that name is not a file.
func Find(dir string) (string, bool) {
	for _, p := range []string{filepath.Join(dir, ".devcontainer", "devcontainer.json"), filepath.Join(dir, ".devcontainer.json")} {
		if fi, err := os.Stat(p); err == nil && fi.Mode().IsRegular() {
			return p, true
		}
	}
	return "", false
}

// Command is one lifecycle command to run in the primary container.
type Command struct {
	Name  string   // "onCreateCommand", or "postCreateCommand.<key>" for an object form
	Shell string   // a string command, run with /bin/sh -c
	Argv  []string // an array command, run as is (exactly one of Shell and Argv is set)
}

// Result is what translation gives the sandbox: the compose files to resolve and what Adele needs beside the model.
type Result struct {
	Files           []string          // compose files for `compose config -f`, in order, absolute
	ProjectDir      string            // compose's --project-directory
	Keep            []string          // services to keep, with their depends_on closure (the caller filters); nil = all
	Primary         string            // the devcontainer's own service
	RemoteUser      string            // remoteUser, else containerUser, else "" (the image's own user)
	RemoteEnv       map[string]string // remoteEnv after substitution; ${containerEnv:X} kept literally
	WorkspaceFolder string            // the folder exec and lifecycle commands run in
	Lifecycle       []Command         // onCreate, updateContent, postCreate, then postStart
	NotRun          []string          // what the file asks for that Adele does not run, named in the verdict
	Unset           []string          // ${localEnv:X} names read with no default, sorted
}

// RefusalError carries a refusal as Translate's error, since compose.Refusal is a record and not an error. Its
// caller takes the refusal with errors.As and answers exactly as for a compose project's.
type RefusalError struct{ Refusal *compose.Refusal }

func (e *RefusalError) Error() string {
	return "devcontainer.json: " + e.Refusal.Setting + " " + e.Refusal.Value + ": " + e.Refusal.Remedy
}

func refuse(setting string, value any, remedy string) *compose.Refusal {
	return &compose.Refusal{Kind: compose.KindSetting, Setting: setting, Value: short(value), Remedy: remedy}
}

func short(v any) string {
	var s string
	switch t := v.(type) {
	case string:
		s = t
	case nil:
	default:
		raw, _ := json.Marshal(t)
		s = string(raw)
	}
	if len(s) > 120 {
		s = s[:117] + "..."
	}
	return s
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

var varRe = regexp.MustCompile(`\$\{([^}]*)\}`)

// subst replaces the variables R12 allows in every string value, recursively; keys are left as written.
type subst struct {
	project, envName string
	unset            map[string]bool
}

func (s *subst) str(v string) string {
	return varRe.ReplaceAllStringFunc(v, func(m string) string {
		inner := m[2 : len(m)-1]
		switch inner {
		case "localWorkspaceFolder", "containerWorkspaceFolder":
			return s.project
		case "localWorkspaceFolderBasename", "containerWorkspaceFolderBasename":
			return filepath.Base(s.project)
		case "devcontainerId":
			return s.envName
		}
		if rest, ok := strings.CutPrefix(inner, "localEnv:"); ok {
			name, def, hasDef := strings.Cut(rest, ":")
			if !hasDef {
				s.unset[name] = true
			}
			return def
		}
		return m // ${containerEnv:X} and forms nobody defined stay literal
	})
}

func (s *subst) value(v any) any {
	switch t := v.(type) {
	case string:
		return s.str(t)
	case []any:
		out := make([]any, len(t))
		for i, e := range t {
			out[i] = s.value(e)
		}
		return out
	case map[string]any:
		out := make(map[string]any, len(t))
		for k, e := range t {
			out[k] = s.value(e)
		}
		return out
	}
	return v
}

// Translate reads the devcontainer.json at path for the project folder projectDir (the folder holding .devcontainer/
// or .devcontainer.json), substitutes variables, applies the refusals and writes the compose file it generates into
// tmpDir. envName is the environment's name (${devcontainerId}); workspace is the agent's workspace, absolute. It
// returns a *RefusalError (its Refusal of kind compose.KindSetting) for anything no grant allows or that cannot be
// translated, a *SyntaxError for a file that does not parse, or another error for an I/O failure.
func Translate(path, projectDir, workspace, envName, tmpDir string) (*Result, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	raw, err := ParseJSONC(data)
	if err != nil {
		return nil, err
	}
	sub := &subst{project: projectDir, envName: envName, unset: map[string]bool{}}
	cfg := sub.value(raw).(map[string]any)
	t := &translator{cfg: cfg, jsonDir: filepath.Dir(path), project: projectDir, workspace: workspace, tmp: tmpDir}
	res, r, err := t.run()
	if err != nil {
		return nil, err
	}
	if r != nil {
		return nil, &RefusalError{Refusal: r}
	}
	for name := range sub.unset {
		res.Unset = append(res.Unset, name)
	}
	sort.Strings(res.Unset)
	return res, nil
}

type translator struct {
	cfg                              map[string]any
	jsonDir, project, workspace, tmp string
	services                         map[string]map[string]any // services in the generated file
	volumes                          map[string]any            // top-level named volumes it declares
}

func (t *translator) run() (*Result, *compose.Refusal, error) {
	res := &Result{}
	for _, k := range sortedKeys(t.cfg) {
		v := t.cfg[k]
		switch {
		case translated[k] || ignored[k]:
		case k == "postAttachCommand":
			if present(v) {
				res.NotRun = append(res.NotRun, "postAttachCommand (no attach)")
			}
		case k == "initializeCommand":
			return nil, refuse(k, v, "initializeCommand runs on the host, which no grant allows; run it yourself in the agent's container"), nil
		case k == "features":
			if present(v) {
				return nil, refuse(k, v, "features are not brokered in slice 1; install what you need in the image or a Dockerfile"), nil
			}
		case k == "appPort":
			return nil, refuse(k, v, "nothing is published on the host; use forwardPorts, which are addresses on "+compose.Network), nil
		default:
			return nil, refuse(k, k, k+" is not brokered; drop it"), nil
		}
	}

	var forms []string
	for _, k := range []string{"image", "build", "dockerComposeFile"} {
		if present(t.cfg[k]) {
			forms = append(forms, k)
		}
	}
	switch len(forms) {
	case 0:
		return nil, refuse("image", "none", "give the devcontainer an image, a build or a dockerComposeFile"), nil
	case 1:
	default:
		return nil, refuse(forms[1], strings.Join(forms, ", "), "give only one of image, build and dockerComposeFile"), nil
	}

	t.services = map[string]map[string]any{}
	t.volumes = map[string]any{}
	composeForm := forms[0] == "dockerComposeFile"
	var file string
	if composeForm {
		files, r := t.composeFiles()
		if r != nil {
			return nil, r, nil
		}
		svc, ok := t.cfg["service"].(string)
		if !ok || svc == "" {
			return nil, refuse("service", t.cfg["service"], "name the service in the compose files that is the devcontainer"), nil
		}
		res.Primary = svc
		res.ProjectDir = filepath.Dir(files[0])
		if rs, ok := t.cfg["runServices"]; ok {
			keep, r := stringList("runServices", rs)
			if r != nil {
				return nil, r, nil
			}
			res.Keep = dedupe(append([]string{svc}, keep...))
		}
		file = filepath.Join(t.tmp, "devcontainer.override.json")
		res.Files = append(files, file)
	} else {
		res.Primary = PrimaryService
		res.ProjectDir = t.project
		file = filepath.Join(t.tmp, "devcontainer.compose.json")
		res.Files = []string{file}
	}
	primary := t.service(res.Primary)
	if !composeForm {
		if r := t.imageOrBuild(primary); r != nil {
			return nil, r, nil
		}
	}
	if r := t.primary(primary, res, composeForm); r != nil {
		return nil, r, nil
	}

	out := map[string]any{}
	svcs := map[string]any{}
	for name, s := range t.services {
		svcs[name] = s
	}
	out["services"] = svcs
	if len(t.volumes) > 0 {
		out["volumes"] = t.volumes
	}
	body, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return nil, nil, err
	}
	if err := os.WriteFile(file, append(body, '\n'), 0o600); err != nil {
		return nil, nil, err
	}
	return res, nil, nil
}

func (t *translator) service(name string) map[string]any {
	s, ok := t.services[name]
	if !ok {
		s = map[string]any{}
		t.services[name] = s
	}
	return s
}

func (t *translator) rel(p string) string {
	if filepath.IsAbs(p) {
		return filepath.Clean(p)
	}
	return filepath.Join(t.jsonDir, p)
}

func (t *translator) composeFiles() ([]string, *compose.Refusal) {
	v := t.cfg["dockerComposeFile"]
	var names []string
	if s, ok := v.(string); ok {
		names = []string{s}
	} else {
		l, r := stringList("dockerComposeFile", v)
		if r != nil {
			return nil, r
		}
		names = l
	}
	var out []string
	for _, n := range names {
		if n == "" {
			return nil, refuse("dockerComposeFile", v, "name each compose file, relative to the devcontainer.json's folder")
		}
		out = append(out, t.rel(n))
	}
	return out, nil
}

func (t *translator) imageOrBuild(s map[string]any) *compose.Refusal {
	if v, ok := t.cfg["image"]; ok && present(v) {
		img, ok := v.(string)
		if !ok {
			return refuse("image", v, "give the image as a string")
		}
		s["image"] = img
		return nil
	}
	b, ok := t.cfg["build"].(map[string]any)
	if !ok {
		return refuse("build", t.cfg["build"], "give build as an object: dockerfile, context, args, target")
	}
	out := map[string]any{}
	ctx := "."
	for _, k := range sortedKeys(b) {
		v := b[k]
		switch k {
		case "context", "dockerfile", "target":
			sv, ok := v.(string)
			if !ok {
				return refuse("build."+k, v, "give build."+k+" as a string")
			}
			switch k {
			case "context":
				if sv != "" {
					ctx = sv
				}
			case "dockerfile":
				if sv != "" {
					out["dockerfile"] = t.rel(sv)
				}
			case "target":
				if sv != "" {
					out["target"] = sv
				}
			}
		case "args":
			args, r := stringMap("build.args", v)
			if r != nil {
				return r
			}
			if len(args) > 0 {
				out["args"] = args
			}
		default:
			return refuse("build."+k, v, "build."+k+" is not brokered; drop it")
		}
	}
	out["context"] = t.rel(ctx)
	s["build"] = out
	return nil
}

// primary maps everything that lands on the devcontainer's own service, and fills res beside it.
func (t *translator) primary(s map[string]any, res *Result, composeForm bool) *compose.Refusal {
	if v, ok := t.cfg["containerEnv"]; ok {
		env, r := stringMap("containerEnv", v)
		if r != nil {
			return r
		}
		for k, e := range env {
			setEnv(s, k, e)
		}
	}
	if v, ok := t.cfg["containerUser"]; ok {
		u, ok := v.(string)
		if !ok {
			return refuse("containerUser", v, "give containerUser as a string")
		}
		if u != "" {
			s["user"] = u
		}
		res.RemoteUser = u
	}
	if v, ok := t.cfg["remoteUser"]; ok {
		u, ok := v.(string)
		if !ok {
			return refuse("remoteUser", v, "give remoteUser as a string")
		}
		if u != "" {
			res.RemoteUser = u
		}
	}
	if v, ok := t.cfg["remoteEnv"]; ok {
		env, r := stringMap("remoteEnv", v)
		if r != nil {
			return r
		}
		res.RemoteEnv = env
	}

	// The workspace mount first, then mounts, as the devcontainer CLI orders them.
	if v, ok := t.cfg["workspaceMount"]; ok && present(v) {
		ws, isStr := v.(string)
		if !isStr {
			return refuse("workspaceMount", v, "give workspaceMount as a mount string")
		}
		vol, r := t.mount("workspaceMount", ws)
		if r != nil {
			return r
		}
		if vol["type"] != "bind" || filepath.Clean(vol["source"].(string)) != filepath.Clean(vol["target"].(string)) {
			return refuse("workspaceMount", ws, "the workspace is mounted at its own absolute path; use source=${localWorkspaceFolder},target=${localWorkspaceFolder},type=bind")
		}
		addVolume(s, vol)
	} else if !composeForm {
		addVolume(s, map[string]any{"type": "bind", "source": t.project, "target": t.project})
	}
	if v, ok := t.cfg["mounts"]; ok {
		l, isList := v.([]any)
		if !isList {
			return refuse("mounts", v, "give mounts as a list")
		}
		for _, m := range l {
			vol, r := t.mount("mounts", m)
			if r != nil {
				return r
			}
			addVolume(s, vol)
		}
	}

	folder := t.project
	if v, ok := t.cfg["workspaceFolder"]; ok {
		f, isStr := v.(string)
		if !isStr {
			return refuse("workspaceFolder", v, "give workspaceFolder as a path")
		}
		if f != "" {
			folder = f
		}
	}
	if !compose.Within(folder, t.workspace) {
		return refuse("workspaceFolder", folder, "use ${localWorkspaceFolder}, or a folder under it: the workspace is mounted at its own path")
	}
	folder = filepath.Clean(folder)
	s["working_dir"] = folder
	res.WorkspaceFolder = folder

	if v, ok := t.cfg["forwardPorts"]; ok {
		l, isList := v.([]any)
		if !isList {
			return refuse("forwardPorts", v, "give forwardPorts as a list of ports")
		}
		for _, p := range l {
			name, port, r := forwardPort(p)
			if r != nil {
				return r
			}
			target := res.Primary
			if name != "" && name != "localhost" && name != res.Primary {
				if !composeForm {
					return refuse("forwardPorts", p, "forward a port of the devcontainer itself: a number, or localhost:<port>")
				}
				target = name
			}
			ts := t.service(target)
			ts["expose"] = append(list(ts["expose"]), strconv.Itoa(port))
		}
	}

	override := !composeForm
	if v, ok := t.cfg["overrideCommand"]; ok {
		b, isBool := v.(bool)
		if !isBool {
			return refuse("overrideCommand", v, "give overrideCommand as true or false")
		}
		override = b
	}
	if override {
		s["entrypoint"] = keepAlive
		s["command"] = []any{}
	}

	for _, k := range []string{"init", "privileged"} {
		if v, ok := t.cfg[k]; ok {
			b, isBool := v.(bool)
			if !isBool {
				return refuse(k, v, "give "+k+" as true or false")
			}
			if b {
				s[k] = true
			}
		}
	}
	for _, kk := range [][2]string{{"capAdd", "cap_add"}, {"securityOpt", "security_opt"}} {
		if v, ok := t.cfg[kk[0]]; ok {
			l, r := stringList(kk[0], v)
			if r != nil {
				return r
			}
			for _, e := range l {
				s[kk[1]] = append(list(s[kk[1]]), e)
			}
		}
	}
	if v, ok := t.cfg["runArgs"]; ok {
		l, r := stringList("runArgs", v)
		if r != nil {
			return r
		}
		if r := t.runArgs(s, l); r != nil {
			return r
		}
	}

	for _, k := range lifecycleKeys {
		cmds, r := lifecycle(k, t.cfg[k])
		if r != nil {
			return r
		}
		res.Lifecycle = append(res.Lifecycle, cmds...)
	}
	return nil
}

func list(v any) []any {
	l, _ := v.([]any)
	return l
}

func setEnv(s map[string]any, k, v string) {
	env, ok := s["environment"].(map[string]any)
	if !ok {
		env = map[string]any{}
		s["environment"] = env
	}
	env[k] = v
}

func addVolume(s map[string]any, vol map[string]any) {
	s["volumes"] = append(list(s["volumes"]), vol)
}

// mount reads one mount, a string "source=..,target=..,type=bind|volume[,readonly]" or an object of those fields,
// into compose's long syntax. A named volume is declared at the top level.
func (t *translator) mount(setting string, v any) (map[string]any, *compose.Refusal) {
	var typ, src, dst string
	ro := false
	switch m := v.(type) {
	case string:
		for _, part := range strings.Split(m, ",") {
			k, val, hasVal := strings.Cut(strings.TrimSpace(part), "=")
			switch k {
			case "type":
				typ = val
			case "source", "src":
				src = val
			case "target", "destination", "dst":
				dst = val
			case "readonly", "ro":
				b, err := strconv.ParseBool(val)
				if hasVal && err != nil {
					return nil, refuse(setting, m, "give readonly as readonly, readonly=true or readonly=false")
				}
				ro = !hasVal || b
			case "consistency":
			case "":
				if strings.TrimSpace(part) != "" {
					return nil, refuse(setting, m, "write the mount as source=...,target=...,type=bind|volume")
				}
			default:
				return nil, refuse(setting, m, "the mount option "+k+" has no checked mapping; drop it")
			}
		}
	case map[string]any:
		for _, k := range sortedKeys(m) {
			switch k {
			case "type", "source", "target":
				sv, ok := m[k].(string)
				if !ok {
					return nil, refuse(setting, m, "give the mount's "+k+" as a string")
				}
				switch k {
				case "type":
					typ = sv
				case "source":
					src = sv
				default:
					dst = sv
				}
			case "readonly":
				b, ok := m[k].(bool)
				if !ok {
					return nil, refuse(setting, m, "give the mount's readonly as true or false")
				}
				ro = b
			default:
				return nil, refuse(setting, m, "the mount field "+k+" has no checked mapping; drop it")
			}
		}
	default:
		return nil, refuse(setting, v, "give the mount as source=...,target=...,type=bind|volume or as an object")
	}
	return t.volume(setting, v, typ, src, dst, ro)
}

func (t *translator) volume(setting string, v any, typ, src, dst string, ro bool) (map[string]any, *compose.Refusal) {
	if dst == "" {
		return nil, refuse(setting, v, "give the mount a target")
	}
	out := map[string]any{"type": typ, "target": dst}
	switch typ {
	case "bind":
		if src == "" {
			return nil, refuse(setting, v, "give the bind mount a source inside the workspace")
		}
		out["source"] = src
	case "volume":
		if src != "" {
			out["source"] = src
			t.volumes[src] = map[string]any{}
		}
	default:
		return nil, refuse(setting, v, "use a bind mount inside the workspace or a named volume")
	}
	if ro {
		out["read_only"] = true
	}
	return out, nil
}

// forwardPort reads a port, a "<port>" string, or "<name>:<port>".
func forwardPort(v any) (string, int, *compose.Refusal) {
	bad := refuse("forwardPorts", v, "give a port as a number, or <service>:<port>")
	var name, num string
	switch p := v.(type) {
	case float64:
		if p != float64(int(p)) {
			return "", 0, bad
		}
		num = strconv.Itoa(int(p))
	case string:
		if n, port, ok := strings.Cut(p, ":"); ok {
			if n == "" {
				return "", 0, bad
			}
			name, num = n, port
		} else {
			num = p
		}
	default:
		return "", 0, bad
	}
	port, err := strconv.Atoi(num)
	if err != nil || port < 1 || port > 65535 {
		return "", 0, bad
	}
	return name, port, nil
}

// runArg is one docker run flag with a checked compose key.
type runArg struct {
	takesValue bool
	apply      func(t *translator, s map[string]any, arg, val string) *compose.Refusal
}

func setKey(key string) func(*translator, map[string]any, string, string) *compose.Refusal {
	return func(_ *translator, s map[string]any, _, val string) *compose.Refusal { s[key] = val; return nil }
}

func appendKey(key string) func(*translator, map[string]any, string, string) *compose.Refusal {
	return func(_ *translator, s map[string]any, _, val string) *compose.Refusal {
		s[key] = append(list(s[key]), val)
		return nil
	}
}

func setTrue(key string) func(*translator, map[string]any, string, string) *compose.Refusal {
	return func(_ *translator, s map[string]any, arg, val string) *compose.Refusal {
		b := true
		if val != "" {
			var err error
			if b, err = strconv.ParseBool(val); err != nil {
				return refuse("runArgs", arg, "give "+arg+" as a flag, or =true or =false")
			}
		}
		if b {
			s[key] = true
		} else {
			delete(s, key)
		}
		return nil
	}
}

var runArgs = map[string]runArg{
	"env": {true, func(_ *translator, s map[string]any, arg, val string) *compose.Refusal {
		k, v, ok := strings.Cut(val, "=")
		if !ok || k == "" {
			return refuse("runArgs", arg+" "+val, "give the variable a value (K=V): K alone would read the agent's environment")
		}
		setEnv(s, k, v)
		return nil
	}},
	"label": {true, func(_ *translator, s map[string]any, _, val string) *compose.Refusal {
		k, v, _ := strings.Cut(val, "=")
		labels, ok := s["labels"].(map[string]any)
		if !ok {
			labels = map[string]any{}
			s["labels"] = labels
		}
		labels[k] = v
		return nil
	}},
	"user":     {true, setKey("user")},
	"workdir":  {true, setKey("working_dir")},
	"hostname": {true, setKey("hostname")},
	"init":     {false, setTrue("init")},
	"shm-size": {true, setKey("shm_size")},
	"memory":   {true, setKey("mem_limit")},
	"cpus": {true, func(_ *translator, s map[string]any, arg, val string) *compose.Refusal {
		f, err := strconv.ParseFloat(val, 64)
		if err != nil || f <= 0 {
			return refuse("runArgs", arg+" "+val, "give --cpus as a positive number")
		}
		s["cpus"] = f
		return nil
	}},
	"add-host": {true, appendKey("extra_hosts")},
	"volume": {true, func(t *translator, s map[string]any, arg, val string) *compose.Refusal {
		parts := strings.Split(val, ":")
		var src, dst string
		ro := false
		switch len(parts) {
		case 1:
			dst = parts[0]
		case 2, 3:
			src, dst = parts[0], parts[1]
			if len(parts) == 3 {
				switch parts[2] {
				case "ro":
					ro = true
				case "rw":
				default:
					return refuse("runArgs", arg+" "+val, "the volume option "+parts[2]+" has no checked mapping; use ro or rw")
				}
			}
		default:
			return refuse("runArgs", arg+" "+val, "write the volume as source:target[:ro]")
		}
		typ := "volume"
		if strings.HasPrefix(src, "/") {
			typ = "bind"
		} else if strings.HasPrefix(src, ".") || strings.Contains(src, "/") {
			return refuse("runArgs", arg+" "+val, "give a bind source as an absolute path inside the workspace, or name a volume")
		}
		vol, r := t.volume("runArgs", arg+" "+val, typ, src, dst, ro)
		if r != nil {
			return r
		}
		addVolume(s, vol)
		return nil
	}},
	"mount": {true, func(t *translator, s map[string]any, arg, val string) *compose.Refusal {
		vol, r := t.mount("runArgs", val)
		if r != nil {
			r.Value = short(arg + " " + val)
			return r
		}
		addVolume(s, vol)
		return nil
	}},
	"cap-add":      {true, appendKey("cap_add")},
	"privileged":   {false, setTrue("privileged")},
	"security-opt": {true, appendKey("security_opt")},
	"device":       {true, appendKey("devices")},
	"network":      {true, setKey("network_mode")},
	"pid":          {true, setKey("pid")},
	"ipc":          {true, setKey("ipc")},
	"uts":          {true, setKey("uts")},
	"userns":       {true, setKey("userns_mode")},
	"name":         {true, setKey("container_name")},
}

var shortFlags = map[string]string{"e": "env", "l": "label", "u": "user", "w": "workdir", "h": "hostname",
	"m": "memory", "v": "volume"}

var longAliases = map[string]string{"net": "network"}

// runArgs maps docker run flags onto compose keys, which slice 0's check then accepts or refuses (R12). A flag with
// no mapping is refused, named.
func (t *translator) runArgs(s map[string]any, args []string) *compose.Refusal {
	for i := 0; i < len(args); i++ {
		arg := args[i]
		var name, val string
		hasVal := false
		switch {
		case strings.HasPrefix(arg, "--"):
			name, val, hasVal = strings.Cut(arg[2:], "=")
			if a, ok := longAliases[name]; ok {
				name = a
			}
		case strings.HasPrefix(arg, "-") && len(arg) >= 2:
			long, ok := shortFlags[arg[1:2]]
			if !ok {
				return refuse("runArgs", arg, arg+" has no checked mapping; drop it")
			}
			name = long
			if rest := arg[2:]; rest != "" {
				val, hasVal = strings.TrimPrefix(rest, "="), true
			}
		default:
			return refuse("runArgs", arg, arg+" has no checked mapping; drop it")
		}
		ra, ok := runArgs[name]
		if !ok {
			return refuse("runArgs", arg, arg+" has no checked mapping; drop it")
		}
		if ra.takesValue && !hasVal {
			if i+1 >= len(args) {
				return refuse("runArgs", arg, "give "+arg+" its value")
			}
			i++
			val = args[i]
		}
		if r := ra.apply(t, s, arg, val); r != nil {
			return r
		}
	}
	return nil
}

// lifecycle reads one lifecycle command: a string, an array, or an object of either in key order (R13).
func lifecycle(key string, v any) ([]Command, *compose.Refusal) {
	one := func(name string, v any) (*Command, *compose.Refusal) {
		switch c := v.(type) {
		case nil:
			return nil, nil
		case string:
			if c == "" {
				return nil, nil
			}
			return &Command{Name: name, Shell: c}, nil
		case []any:
			argv, r := stringList(key, c)
			if r != nil {
				return nil, r
			}
			if len(argv) == 0 {
				return nil, nil
			}
			return &Command{Name: name, Argv: argv}, nil
		}
		return nil, refuse(key, v, "give "+key+" as a string, an array of strings, or an object of those")
	}
	obj, ok := v.(map[string]any)
	if !ok {
		c, r := one(key, v)
		if r != nil || c == nil {
			return nil, r
		}
		return []Command{*c}, nil
	}
	var out []Command
	for _, k := range sortedKeys(obj) {
		if _, nested := obj[k].(map[string]any); nested {
			return nil, refuse(key, obj[k], "give each of "+key+"'s commands as a string or an array of strings")
		}
		c, r := one(key+"."+k, obj[k])
		if r != nil {
			return nil, r
		}
		if c != nil {
			out = append(out, *c)
		}
	}
	return out, nil
}

func stringList(setting string, v any) ([]string, *compose.Refusal) {
	l, ok := v.([]any)
	if !ok {
		return nil, refuse(setting, v, "give "+setting+" as a list of strings")
	}
	out := make([]string, 0, len(l))
	for _, e := range l {
		s, ok := e.(string)
		if !ok {
			return nil, refuse(setting, v, "give "+setting+" as a list of strings")
		}
		out = append(out, s)
	}
	return out, nil
}

// stringMap reads an object of strings; a null value is dropped (the devcontainer form of unsetting).
func stringMap(setting string, v any) (map[string]string, *compose.Refusal) {
	obj, ok := v.(map[string]any)
	if !ok {
		return nil, refuse(setting, v, "give "+setting+" as an object of strings")
	}
	out := make(map[string]string, len(obj))
	for k, e := range obj {
		switch s := e.(type) {
		case nil:
		case string:
			out[k] = s
		default:
			return nil, refuse(setting, fmt.Sprintf("%s: %s", k, short(e)), "give "+setting+"."+k+" as a string")
		}
	}
	return out, nil
}

func dedupe(in []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, s := range in {
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return out
}
