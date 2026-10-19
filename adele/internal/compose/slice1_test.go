package compose

import (
	"testing"
	"time"

	"timelike/adele/internal/engine"
)

// A build is brokered in slice 1 with its context, Dockerfile, args, target and labels; its default network is fine.
func TestCheckAllowsABuildInsideTheWorkspace(t *testing.T) {
	m := model(t, `{"name": "p", "services": {"app": {"build": {"context": "/w/ws1/p", "dockerfile": "Dockerfile",
	  "args": {"BASE": "debian:x"}, "target": "dev", "network": "default", "labels": {"a": "b"}}}}}`)
	if r := Check(m, ws, map[string]string{}); r != nil {
		t.Fatalf("refused: %+v", r)
	}
	b := Builds(m)
	if len(b) != 1 || b[0].Service != "app" || b[0].Context != "/w/ws1/p" || b[0].Dockerfile != "/w/ws1/p/Dockerfile" ||
		b[0].Args["BASE"] != "debian:x" || b[0].Target != "dev" {
		t.Fatalf("Builds = %+v", b)
	}
	if Check(model(t, `{"name": "p", "services": {"app": {}}}`), ws, nil) == nil {
		t.Fatal("a service with neither image nor build was allowed")
	}
}

func TestBuildsReadsListArgsAndAnAbsoluteDockerfile(t *testing.T) {
	b := Builds(model(t, `{"services": {"x": {"build": {"context": "/w/ws1/p", "dockerfile": "/w/ws1/df/D", "args": ["A=1", "B=2"]}}}}`))
	if len(b) != 1 || b[0].Dockerfile != "/w/ws1/df/D" || b[0].Args["A"] != "1" || b[0].Args["B"] != "2" {
		t.Fatalf("Builds = %+v", b)
	}
}

// The model's hash moves when a build's key does, and only then (D-12, cross-stack P003).
func TestTheHashCoversTheBuildKey(t *testing.T) {
	m := model(t, `{"services": {"app": {"build": {"context": "/w/ws1/p"}}}}`)
	a, b := Hash(WithBuildKeys(m, map[string]string{"app": "k1"})), Hash(WithBuildKeys(m, map[string]string{"app": "k2"}))
	if a == b || a != Hash(WithBuildKeys(m, map[string]string{"app": "k1"})) {
		t.Fatal("the hash does not follow the build key")
	}
	if _, ok := m["services"].(map[string]any)["app"].(map[string]any)["x-timelike-build-key"]; ok {
		t.Fatal("WithBuildKeys changed the model it was given")
	}
}

// Everything an environment creates carries session, grant and requester (R21); a certain one-shot is marked (R20);
// a devcontainer's primary carries what exec needs (R12); a built service runs the image its build made.
func TestInjectLabelsSessionGrantRequesterOneShotsAndTheDevcontainer(t *testing.T) {
	m := model(t, `{"services": {
	  "seed": {"image": "debian:x"},
	  "dev": {"build": {"context": "/w/ws1/p"}, "depends_on": {"seed": {"condition": "service_completed_successfully", "required": true}}}},
	  "volumes": {"data": {}}}`)
	raw, err := Inject(m, "tl-p-1", time.Unix(0, 0), time.Hour, "h", Meta{Session: "s1", Grant: "g1", Requester: "c1",
		Images: map[string]string{"dev": "tl-p-1-dev:abc"}, Primary: "dev", RemoteUser: "u", Workdir: "/w/ws1/p", RemoteEnv: `{"A":"1"}`})
	if err != nil {
		t.Fatal(err)
	}
	out := model(t, string(raw))
	svcs := out["services"].(map[string]any)
	dev, seed := svcs["dev"].(map[string]any), svcs["seed"].(map[string]any)
	if _, ok := dev["build"]; ok || dev["image"] != "tl-p-1-dev:abc" {
		t.Fatalf("dev: %v", dev)
	}
	dl, sl := dev["labels"].(map[string]any), seed["labels"].(map[string]any)
	for _, l := range []map[string]any{dl, sl} {
		if l[engine.LabelSession] != "s1" || l[engine.LabelGrant] != "g1" || l[engine.LabelRequester] != "c1" {
			t.Fatalf("labels %v", l)
		}
	}
	if sl[engine.LabelOneShot] != "1" || dl[engine.LabelOneShot] != nil {
		t.Fatalf("one-shot: seed %v, dev %v", sl[engine.LabelOneShot], dl[engine.LabelOneShot])
	}
	if dl[engine.LabelDevcontainer] != "1" || dl[engine.LabelRemoteUser] != "u" || dl[engine.LabelWorkdir] != "/w/ws1/p" ||
		dl[engine.LabelRemoteEnv] != `{"A":"1"}` || sl[engine.LabelDevcontainer] != nil {
		t.Fatalf("devcontainer labels: dev %v seed %v", dl, sl)
	}
	vl := out["volumes"].(map[string]any)["data"].(map[string]any)["labels"].(map[string]any)
	nl := out["networks"].(map[string]any)["default"].(map[string]any)["labels"].(map[string]any)
	for _, l := range []map[string]any{vl, nl} {
		if l[engine.LabelSession] != "s1" || l[engine.LabelGrant] != "g1" || l[engine.LabelEnv] != "tl-p-1" {
			t.Fatalf("network/volume labels %v", l)
		}
	}
}

// A remoteEnv holding ${containerEnv:X} reaches compose escaped, so compose's interpolation reads it back unchanged.
func TestInjectEscapesTheDollarsInAdelesOwnLabels(t *testing.T) {
	m := model(t, `{"services": {"dev": {"image": "debian:x"}}}`)
	raw, err := Inject(m, "tl-p-1", time.Unix(0, 0), time.Hour, "h", Meta{Primary: "dev", RemoteEnv: `{"P":"${containerEnv:PATH}:/x"}`})
	if err != nil {
		t.Fatal(err)
	}
	l := model(t, string(raw))["services"].(map[string]any)["dev"].(map[string]any)["labels"].(map[string]any)
	if l[engine.LabelRemoteEnv] != `{"P":"$${containerEnv:PATH}:/x"}` {
		t.Fatalf("remote-env label %q", l[engine.LabelRemoteEnv])
	}
}
