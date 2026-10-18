package devcontainer

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"timelike/adele/internal/compose"
)

// project makes a workspace with a project folder in it and writes body as its .devcontainer/devcontainer.json.
func project(t *testing.T, body string) (ws, dir, path string) {
	t.Helper()
	ws = t.TempDir()
	dir = filepath.Join(ws, "proj")
	if err := os.MkdirAll(filepath.Join(dir, ".devcontainer"), 0o755); err != nil {
		t.Fatal(err)
	}
	path = filepath.Join(dir, ".devcontainer", "devcontainer.json")
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return ws, dir, path
}

func translate(t *testing.T, body string) (*Result, error, string, string) {
	t.Helper()
	ws, dir, path := project(t, body)
	res, err := Translate(path, dir, ws, "tl-proj-abc123", t.TempDir())
	return res, err, ws, dir
}

func ok(t *testing.T, body string) (*Result, map[string]any, string, string) {
	t.Helper()
	res, err, ws, dir := translate(t, body)
	if err != nil {
		t.Fatalf("Translate: %v", err)
	}
	raw, err := os.ReadFile(res.Files[len(res.Files)-1])
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("generated file is not JSON: %v", err)
	}
	return res, doc, ws, dir
}

func refused(t *testing.T, body, setting string) *compose.Refusal {
	t.Helper()
	_, err, _, _ := translate(t, body)
	var re *RefusalError
	if !errors.As(err, &re) {
		t.Fatalf("want a refusal of %s, got %v", setting, err)
	}
	if re.Refusal.Kind != compose.KindSetting || re.Refusal.Setting != setting || re.Refusal.Remedy == "" {
		t.Fatalf("want a setting refusal of %s, got %+v", setting, re.Refusal)
	}
	return re.Refusal
}

func svc(doc map[string]any, name string) map[string]any {
	s, _ := doc["services"].(map[string]any)[name].(map[string]any)
	return s
}

func TestFind(t *testing.T) {
	dir := t.TempDir()
	if _, found := Find(dir); found {
		t.Fatal("found a devcontainer in an empty folder")
	}
	root := filepath.Join(dir, ".devcontainer.json")
	if err := os.WriteFile(root, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	if p, found := Find(dir); !found || p != root {
		t.Fatalf("Find = %q %v", p, found)
	}
	nested := filepath.Join(dir, ".devcontainer", "devcontainer.json")
	if err := os.MkdirAll(filepath.Dir(nested), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(nested, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	if p, found := Find(dir); !found || p != nested {
		t.Fatalf("Find prefers .devcontainer/devcontainer.json; got %q %v", p, found)
	}
}

func TestParseJSONC(t *testing.T) {
	src := `// a leading comment
{
  /* a block
     comment */ "image": "alpine", // trailing
  "url": "http://example.test//x", "c": "/* not a comment */",
  "esc": "a\"//b",
  "list": [1, 2, 3,],
  "obj": {"k": "v",},
}
`
	got, err := ParseJSONC([]byte(src))
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]any{"image": "alpine", "url": "http://example.test//x", "c": "/* not a comment */",
		"esc": `a"//b`, "list": []any{1.0, 2.0, 3.0}, "obj": map[string]any{"k": "v"}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v\nwant %v", got, want)
	}
	if b := blank([]byte(src)); len(b) != len(src) || strings.Count(string(b), "\n") != strings.Count(src, "\n") {
		t.Fatal("blanking changed the length or the lines")
	}
}

func TestParseJSONCLine(t *testing.T) {
	src := "{\n  // one\n  \"a\": 1,\n  /* two\n */ \"b\": 2\n  \"c\": 3\n}\n"
	_, err := ParseJSONC([]byte(src))
	var se *SyntaxError
	if !errors.As(err, &se) || se.Line != 6 {
		t.Fatalf("want a syntax error on line 6, got %v", err)
	}
	if !strings.HasPrefix(err.Error(), "devcontainer.json line 6: ") {
		t.Fatalf("message %q", err.Error())
	}
	src5 := "{\n  \"a\": 1,\n  \"b\": 2,\n  \"c\": 3\n  \"d\": 4\n}\n"
	if _, err := ParseJSONC([]byte(src5)); !errors.As(err, &se) || se.Line != 5 {
		t.Fatalf("missing comma: want line 5, got %v", err)
	}
	if _, err := ParseJSONC([]byte("{\n\"a\": 1,\n")); !errors.As(err, &se) || se.Line != 2 {
		t.Fatalf("truncated: want line 2, where the text ends, got %v", err)
	}
	for _, s := range []string{"[1]", `"x"`, "null"} {
		if _, err := ParseJSONC([]byte(s)); !errors.As(err, &se) {
			t.Fatalf("%s: want a syntax error, got %v", s, err)
		}
	}
}

func TestTranslateSyntaxError(t *testing.T) {
	_, err, _, _ := translate(t, "{\n\"image\": \"a\"\n\"x\": 1}")
	var se *SyntaxError
	if !errors.As(err, &se) || se.Line != 3 {
		t.Fatalf("want a syntax error on line 3, got %v", err)
	}
	if _, err := Translate(filepath.Join(t.TempDir(), "missing.json"), "/p", "/p", "tl-x", t.TempDir()); err == nil ||
		errors.As(err, &se) {
		t.Fatalf("a missing file is an I/O error, got %v", err)
	}
}

func TestVariables(t *testing.T) {
	res, doc, _, dir := ok(t, `{
  "image": "alpine",
  "containerEnv": {"A": "${localWorkspaceFolder}", "B": "${containerWorkspaceFolderBasename}",
    "C": "${devcontainerId}", "D": "x${localEnv:HOME}y", "E": "${localEnv:TOKEN:dflt:z}", "F": "${unknown}",
    "G": "${localWorkspaceFolderBasename}-${containerWorkspaceFolder}", "H": "${containerEnv:PATH}"},
  "remoteEnv": {"PATH": "${containerEnv:PATH}:/x", "U": "${localEnv:USER}", "N": null},
  "customizations": {"vscode": {"${localEnv:NOT_READ_KEY}": 1}}
}`)
	env := svc(doc, "devcontainer")["environment"].(map[string]any)
	want := map[string]any{"A": dir, "B": "proj", "C": "tl-proj-abc123", "D": "xy", "E": "dflt:z", "F": "${unknown}",
		"G": "proj-" + dir, "H": "${containerEnv:PATH}"}
	if !reflect.DeepEqual(env, want) {
		t.Fatalf("environment %v\nwant %v", env, want)
	}
	if !reflect.DeepEqual(res.RemoteEnv, map[string]string{"PATH": "${containerEnv:PATH}:/x", "U": ""}) {
		t.Fatalf("remoteEnv %v", res.RemoteEnv)
	}
	if !reflect.DeepEqual(res.Unset, []string{"HOME", "USER"}) {
		t.Fatalf("Unset %v (keys are never substituted)", res.Unset)
	}
}

func TestImageForm(t *testing.T) {
	res, doc, _, dir := ok(t, `{"name": "x", "image": "alpine:3", "containerUser": "app", "init": true,
		"forwardPorts": [8080, "9090", "localhost:7000", "devcontainer:7001"], "$schema": "s", "waitFor": "x"}`)
	if res.Primary != "devcontainer" || res.ProjectDir != dir || res.Keep != nil || len(res.Files) != 1 ||
		filepath.Base(res.Files[0]) != "devcontainer.compose.json" || !filepath.IsAbs(res.Files[0]) {
		t.Fatalf("result %+v", res)
	}
	if fi, err := os.Stat(res.Files[0]); err != nil || fi.Mode().Perm() != 0o600 {
		t.Fatalf("generated file mode: %v %v", fi, err)
	}
	if res.RemoteUser != "app" || res.WorkspaceFolder != dir {
		t.Fatalf("remote user %q, folder %q", res.RemoteUser, res.WorkspaceFolder)
	}
	s := svc(doc, "devcontainer")
	want := map[string]any{
		"image": "alpine:3", "user": "app", "init": true, "working_dir": dir,
		"volumes":    []any{map[string]any{"type": "bind", "source": dir, "target": dir}},
		"expose":     []any{"8080", "9090", "7000", "7001"},
		"entrypoint": []any{"/bin/sh", "-c", "trap 'exit 0' TERM; while sleep 1000 & wait $!; do :; done"},
		"command":    []any{},
	}
	if !reflect.DeepEqual(s, want) {
		t.Fatalf("service %v\nwant %v", s, want)
	}
	if _, has := doc["volumes"]; has {
		t.Fatal("no named volume, so no top-level volumes")
	}
	refused(t, `{"image": "a", "forwardPorts": ["db:5432"]}`, "forwardPorts")
	refused(t, `{"image": "a", "forwardPorts": [70000]}`, "forwardPorts")
	refused(t, `{"image": "a", "forwardPorts": [true]}`, "forwardPorts")
}

func TestRemoteUserAndOverride(t *testing.T) {
	res, doc, _, _ := ok(t, `{"image": "a", "containerUser": "c", "remoteUser": "r", "overrideCommand": false}`)
	if res.RemoteUser != "r" {
		t.Fatalf("remoteUser %q", res.RemoteUser)
	}
	if s := svc(doc, "devcontainer"); s["entrypoint"] != nil || s["command"] != nil {
		t.Fatalf("overrideCommand false kept the image's command: %v", s)
	}
	res, _, _, _ = ok(t, `{"image": "a"}`)
	if res.RemoteUser != "" {
		t.Fatalf("no user given: %q", res.RemoteUser)
	}
	refused(t, `{"image": "a", "overrideCommand": "yes"}`, "overrideCommand")
}

func TestBuildForm(t *testing.T) {
	res, doc, _, dir := ok(t, `{"build": {"dockerfile": "Dockerfile", "context": "..", "args": {"V": "1"}, "target": "dev"}}`)
	b := svc(doc, "devcontainer")["build"].(map[string]any)
	want := map[string]any{"dockerfile": filepath.Join(dir, ".devcontainer", "Dockerfile"), "context": dir,
		"args": map[string]any{"V": "1"}, "target": "dev"}
	if !reflect.DeepEqual(b, want) || res.Primary != "devcontainer" {
		t.Fatalf("build %v\nwant %v", b, want)
	}
	_, doc, _, dir = ok(t, `{"build": {"dockerfile": "Dockerfile"}}`)
	if c := svc(doc, "devcontainer")["build"].(map[string]any)["context"]; c != filepath.Join(dir, ".devcontainer") {
		t.Fatalf("default context %v", c)
	}
	refused(t, `{"build": {"dockerfile": "D", "cacheFrom": "x"}}`, "build.cacheFrom")
	refused(t, `{"build": "Dockerfile"}`, "build")
	refused(t, `{"image": "a", "build": {"dockerfile": "D"}}`, "build")
	refused(t, `{"name": "x"}`, "image")
}

func TestWorkspaceMountAndFolder(t *testing.T) {
	_, doc, _, dir := ok(t, `{"image": "a",
		"workspaceMount": "source=${localWorkspaceFolder},target=${localWorkspaceFolder},type=bind,consistency=cached",
		"workspaceFolder": "${localWorkspaceFolder}/sub"}`)
	s := svc(doc, "devcontainer")
	if v := s["volumes"].([]any); len(v) != 1 || !reflect.DeepEqual(v[0], map[string]any{"type": "bind", "source": dir, "target": dir}) {
		t.Fatalf("volumes %v", v)
	}
	if s["working_dir"] != filepath.Join(dir, "sub") {
		t.Fatalf("working_dir %v", s["working_dir"])
	}
	refused(t, `{"image": "a", "workspaceMount": "source=${localWorkspaceFolder},target=/workspace,type=bind"}`, "workspaceMount")
	refused(t, `{"image": "a", "workspaceMount": "source=v,target=v,type=volume"}`, "workspaceMount")
	r := refused(t, `{"image": "a", "workspaceFolder": "/workspace"}`, "workspaceFolder")
	if !strings.Contains(r.Remedy, "${localWorkspaceFolder}") || r.Value != "/workspace" {
		t.Fatalf("refusal %+v", r)
	}
	refused(t, `{"image": "a", "workspaceFolder": "relative"}`, "workspaceFolder")
}

func TestMounts(t *testing.T) {
	_, doc, _, dir := ok(t, `{"image": "a", "mounts": [
		"source=${localWorkspaceFolder}/data,target=/data,type=bind,readonly",
		"source=cache-${devcontainerId},target=/cache,type=volume",
		{"source": "objvol", "target": "/o", "type": "volume"},
		{"source": "/x", "target": "/y", "type": "bind", "readonly": true},
		"target=/anon,type=volume"]}`)
	v := svc(doc, "devcontainer")["volumes"].([]any)
	want := []any{
		map[string]any{"type": "bind", "source": dir, "target": dir},
		map[string]any{"type": "bind", "source": dir + "/data", "target": "/data", "read_only": true},
		map[string]any{"type": "volume", "source": "cache-tl-proj-abc123", "target": "/cache"},
		map[string]any{"type": "volume", "source": "objvol", "target": "/o"},
		map[string]any{"type": "bind", "source": "/x", "target": "/y", "read_only": true},
		map[string]any{"type": "volume", "target": "/anon"},
	}
	if !reflect.DeepEqual(v, want) {
		t.Fatalf("volumes %v\nwant %v", v, want)
	}
	if !reflect.DeepEqual(doc["volumes"], map[string]any{"cache-tl-proj-abc123": map[string]any{}, "objvol": map[string]any{}}) {
		t.Fatalf("top-level volumes %v", doc["volumes"])
	}
	refused(t, `{"image": "a", "mounts": ["source=a,target=/t,type=tmpfs"]}`, "mounts")
	refused(t, `{"image": "a", "mounts": ["source=a,target=/t,type=volume,bogus=1"]}`, "mounts")
	refused(t, `{"image": "a", "mounts": ["source=a,type=volume"]}`, "mounts")
	refused(t, `{"image": "a", "mounts": [{"source": "a", "target": "/t", "type": "volume", "extra": 1}]}`, "mounts")
	refused(t, `{"image": "a", "mounts": "x"}`, "mounts")
}

func TestPassedToCheck(t *testing.T) {
	_, doc, _, _ := ok(t, `{"image": "a", "privileged": true, "capAdd": ["SYS_ADMIN"], "securityOpt": ["seccomp=unconfined"]}`)
	s := svc(doc, "devcontainer")
	if s["privileged"] != true || !reflect.DeepEqual(s["cap_add"], []any{"SYS_ADMIN"}) ||
		!reflect.DeepEqual(s["security_opt"], []any{"seccomp=unconfined"}) {
		t.Fatalf("service %v: these are slice 0's to refuse", s)
	}
}

func TestRunArgs(t *testing.T) {
	_, doc, _, _ := ok(t, `{"image": "a", "containerEnv": {"A": "1"}, "runArgs": [
		"-e", "B=2", "--env=C=3", "-eD=4", "--label", "k=v", "-u", "1000", "--workdir=/w", "-h", "box",
		"--init", "--shm-size", "1g", "-m", "512m", "--cpus=1.5", "--add-host", "h:10.0.0.1",
		"-v", "/src:/dst:ro", "--volume=named:/n", "--mount", "type=volume,source=mv,target=/mv",
		"--cap-add", "NET_ADMIN", "--privileged", "--security-opt", "no-new-privileges",
		"--device", "/dev/fuse", "--net", "host", "--pid=host", "--ipc", "host", "--uts", "host",
		"--userns", "host", "--name", "fixed"]}`)
	s := svc(doc, "devcontainer")
	checks := map[string]any{
		"environment":    map[string]any{"A": "1", "B": "2", "C": "3", "D": "4"},
		"labels":         map[string]any{"k": "v"},
		"user":           "1000",
		"working_dir":    "/w",
		"hostname":       "box",
		"init":           true,
		"shm_size":       "1g",
		"mem_limit":      "512m",
		"cpus":           1.5,
		"extra_hosts":    []any{"h:10.0.0.1"},
		"cap_add":        []any{"NET_ADMIN"},
		"privileged":     true,
		"security_opt":   []any{"no-new-privileges"},
		"devices":        []any{"/dev/fuse"},
		"network_mode":   "host",
		"pid":            "host",
		"ipc":            "host",
		"uts":            "host",
		"userns_mode":    "host",
		"container_name": "fixed",
	}
	for k, want := range checks {
		if !reflect.DeepEqual(s[k], want) {
			t.Errorf("%s = %v, want %v", k, s[k], want)
		}
	}
	vols := s["volumes"].([]any)
	if len(vols) != 4 ||
		!reflect.DeepEqual(vols[1], map[string]any{"type": "bind", "source": "/src", "target": "/dst", "read_only": true}) ||
		!reflect.DeepEqual(vols[2], map[string]any{"type": "volume", "source": "named", "target": "/n"}) ||
		!reflect.DeepEqual(vols[3], map[string]any{"type": "volume", "source": "mv", "target": "/mv"}) {
		t.Errorf("volumes %v", vols)
	}
	if !reflect.DeepEqual(doc["volumes"], map[string]any{"named": map[string]any{}, "mv": map[string]any{}}) {
		t.Errorf("top-level volumes %v", doc["volumes"])
	}

	r := refused(t, `{"image": "a", "runArgs": ["--rm"]}`, "runArgs")
	if r.Value != "--rm" || !strings.Contains(r.Remedy, "no checked mapping") {
		t.Fatalf("refusal %+v", r)
	}
	refused(t, `{"image": "a", "runArgs": ["-it"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["positional"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["-e", "FROM_AGENT"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["--user"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["-v", "./rel:/x"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["-v", "/a:/b:z"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["--cpus", "lots"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": ["--mount", "type=tmpfs,target=/t"]}`, "runArgs")
	refused(t, `{"image": "a", "runArgs": "--rm"}`, "runArgs")
}

func TestRefusedKeys(t *testing.T) {
	for key, body := range map[string]string{
		"initializeCommand": `{"image": "a", "initializeCommand": "echo hi"}`,
		"features":          `{"image": "a", "features": {"ghcr.io/x/y:1": {}}}`,
		"appPort":           `{"image": "a", "appPort": [3000]}`,
		"dockerFile":        `{"image": "a", "dockerFile": "Dockerfile"}`,
	} {
		refused(t, body, key)
	}
	if r := refused(t, `{"image": "a", "initializeCommand": "x"}`, "initializeCommand"); !strings.Contains(r.Remedy, "host") {
		t.Fatalf("remedy %q", r.Remedy)
	}
	if r := refused(t, `{"image": "a", "appPort": 3000}`, "appPort"); !strings.Contains(r.Remedy, compose.Network) {
		t.Fatalf("remedy %q", r.Remedy)
	}
	ok(t, `{"image": "a", "features": {}}`)
}

func TestLifecycle(t *testing.T) {
	res, _, _, _ := ok(t, `{"image": "a",
		"postStartCommand": "start",
		"postCreateCommand": {"b": ["npm", "ci"], "a": "make", "empty": ""},
		"updateContentCommand": ["echo", "update"],
		"onCreateCommand": "echo created",
		"postAttachCommand": "attach"}`)
	want := []Command{
		{Name: "onCreateCommand", Shell: "echo created"},
		{Name: "updateContentCommand", Argv: []string{"echo", "update"}},
		{Name: "postCreateCommand.a", Shell: "make"},
		{Name: "postCreateCommand.b", Argv: []string{"npm", "ci"}},
		{Name: "postStartCommand", Shell: "start"},
	}
	if !reflect.DeepEqual(res.Lifecycle, want) {
		t.Fatalf("lifecycle %+v\nwant %+v", res.Lifecycle, want)
	}
	if !reflect.DeepEqual(res.NotRun, []string{"postAttachCommand (no attach)"}) {
		t.Fatalf("NotRun %v", res.NotRun)
	}
	res, _, _, _ = ok(t, `{"image": "a", "onCreateCommand": "", "postStartCommand": []}`)
	if len(res.Lifecycle) != 0 || len(res.NotRun) != 0 {
		t.Fatalf("empty commands: %+v %v", res.Lifecycle, res.NotRun)
	}
	refused(t, `{"image": "a", "onCreateCommand": 1}`, "onCreateCommand")
	refused(t, `{"image": "a", "postCreateCommand": ["a", 1]}`, "postCreateCommand")
	refused(t, `{"image": "a", "postCreateCommand": {"x": {"y": "z"}}}`, "postCreateCommand")
}

func TestComposeForm(t *testing.T) {
	res, doc, ws, dir := ok(t, `{
		"dockerComposeFile": ["../compose.yaml", "compose.dev.yaml"],
		"service": "app",
		"runServices": ["db", "app", "cache"],
		"containerEnv": {"A": "1"},
		"containerUser": "node",
		"mounts": ["source=v,target=/v,type=volume"],
		"forwardPorts": [3000, "db:5432", "localhost:3001"],
		"runArgs": ["--cap-add", "SYS_PTRACE"]
	}`)
	_ = ws
	wantFiles := []string{filepath.Join(dir, "compose.yaml"), filepath.Join(dir, ".devcontainer", "compose.dev.yaml")}
	if len(res.Files) != 3 || !reflect.DeepEqual(res.Files[:2], wantFiles) ||
		filepath.Base(res.Files[2]) != "devcontainer.override.json" {
		t.Fatalf("files %v", res.Files)
	}
	if res.ProjectDir != dir || res.Primary != "app" || !reflect.DeepEqual(res.Keep, []string{"app", "db", "cache"}) {
		t.Fatalf("result %+v", res)
	}
	app := svc(doc, "app")
	want := map[string]any{
		"environment": map[string]any{"A": "1"}, "user": "node", "working_dir": dir,
		"volumes": []any{map[string]any{"type": "volume", "source": "v", "target": "/v"}},
		"expose":  []any{"3000", "3001"}, "cap_add": []any{"SYS_PTRACE"},
	}
	if !reflect.DeepEqual(app, want) {
		t.Fatalf("override for app %v\nwant %v", app, want)
	}
	if !reflect.DeepEqual(svc(doc, "db"), map[string]any{"expose": []any{"5432"}}) {
		t.Fatalf("override for db %v", svc(doc, "db"))
	}
	if !reflect.DeepEqual(doc["volumes"], map[string]any{"v": map[string]any{}}) {
		t.Fatalf("top-level volumes %v", doc["volumes"])
	}

	res, doc, _, dir = ok(t, `{"dockerComposeFile": "compose.yaml", "service": "app", "overrideCommand": true,
		"workspaceMount": "source=${localWorkspaceFolder},target=${localWorkspaceFolder},type=bind"}`)
	if res.Keep != nil || res.ProjectDir != filepath.Join(dir, ".devcontainer") {
		t.Fatalf("no runServices: keep all; got %+v", res)
	}
	app = svc(doc, "app")
	if app["entrypoint"] == nil || len(app["volumes"].([]any)) != 1 {
		t.Fatalf("override %v", app)
	}

	refused(t, `{"dockerComposeFile": "compose.yaml"}`, "service")
	refused(t, `{"dockerComposeFile": ["compose.yaml", 1], "service": "app"}`, "dockerComposeFile")
	refused(t, `{"dockerComposeFile": "compose.yaml", "service": "app", "runServices": "db"}`, "runServices")
	refused(t, `{"dockerComposeFile": "compose.yaml", "service": "app", "workspaceFolder": "/elsewhere"}`, "workspaceFolder")
}

func TestComposeFormNoDefaultMount(t *testing.T) {
	_, doc, _, _ := ok(t, `{"dockerComposeFile": "compose.yaml", "service": "app"}`)
	if app := svc(doc, "app"); app["volumes"] != nil || app["entrypoint"] != nil {
		t.Fatalf("compose form: no default mount, overrideCommand false: %v", app)
	}
}

func TestTypeRefusals(t *testing.T) {
	for setting, body := range map[string]string{
		"image":           `{"image": 1}`,
		"containerEnv":    `{"image": "a", "containerEnv": {"A": 1}}`,
		"remoteEnv":       `{"image": "a", "remoteEnv": []}`,
		"containerUser":   `{"image": "a", "containerUser": 1}`,
		"remoteUser":      `{"image": "a", "remoteUser": 1}`,
		"workspaceMount":  `{"image": "a", "workspaceMount": 1}`,
		"workspaceFolder": `{"image": "a", "workspaceFolder": 1}`,
		"init":            `{"image": "a", "init": "yes"}`,
		"capAdd":          `{"image": "a", "capAdd": "X"}`,
		"forwardPorts":    `{"image": "a", "forwardPorts": 80}`,
		"build.target":    `{"build": {"target": 1}}`,
		"build.args":      `{"build": {"args": {"A": 1}}}`,
	} {
		refused(t, body, setting)
	}
}

func TestRefusalErrorText(t *testing.T) {
	_, err, _, _ := translate(t, `{"image": "a", "appPort": 3000}`)
	if err == nil || !strings.HasPrefix(err.Error(), "devcontainer.json: appPort 3000: ") {
		t.Fatalf("error %v", err)
	}
}
