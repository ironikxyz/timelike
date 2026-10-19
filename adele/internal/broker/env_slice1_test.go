package broker

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"timelike/adele/internal/engine"
)

// What exec decides before the daemon is asked (the daemon's side is the e2e lane's, as for up).
func TestExecIsRefusedBeforeTheDaemonWhenItCannotBeRight(t *testing.T) {
	f := envFixture(t, "/w")
	req := envReq("exec", "tl-p-1", "")
	if out := f.handle(req); out.Status != http.StatusBadRequest || !strings.Contains(out.Body["error"].(string), "needs a command") {
		t.Errorf("no command: %d %v", out.Status, out.Body)
	}
	req.Params.Cmd = []string{"true"}
	req.Params.TimeoutS = 3600
	if out := f.handle(req); out.Status != http.StatusBadRequest || !strings.Contains(out.Body["error"].(string), "at most") {
		t.Errorf("a bound past the most: %d %v", out.Status, out.Body)
	}
	req.Params.TimeoutS = 0
	if out := f.handle(req); out.Status != http.StatusNotFound || !strings.Contains(out.Body["error"].(string), "no live environment") {
		t.Errorf("no environment: %d %v", out.Status, out.Body)
	}
	if n := len(f.rows(t)); n != 0 {
		t.Errorf("%d ledger rows for exec requests that ran nothing", n)
	}
}

func TestExecIsAnActionOfDockerCompose(t *testing.T) {
	if _, bad := validate(Request{Session: "s", Capability: "docker.compose", Action: "exec", Params: Params{Name: "tl-p-1"}}); bad {
		t.Fatal("exec is not a docker.compose action")
	}
}

// remoteEnv without ${containerEnv:X} needs nothing of the daemon; with it, the container's own value or the default.
func TestRemoteEnvIsReadFromTheContainersLabel(t *testing.T) {
	e := &Envs{Engine: engine.New("/nonexistent/docker.sock")}
	env, err := e.remoteEnv(context.Background(), engine.Container{Labels: map[string]string{
		engine.LabelRemoteEnv: `{"B":"2","A":"1"}`}})
	if err != nil || strings.Join(env, ",") != "A=1,B=2" {
		t.Fatalf("remoteEnv = %v, %v", env, err)
	}
	if env, err := e.remoteEnv(context.Background(), engine.Container{}); err != nil || env != nil {
		t.Fatalf("no label: %v, %v", env, err)
	}
	if _, err := e.remoteEnv(context.Background(), engine.Container{Labels: map[string]string{engine.LabelRemoteEnv: "{"}}); err == nil {
		t.Fatal("a broken label read as an environment")
	}
}

func TestTheContextSandboxsDigestIsItsLastStderrLine(t *testing.T) {
	if d := contextDigest([]byte("warning: x\n{\"digest\":\"abc\",\"entries\":3}\n")); d != "abc" {
		t.Fatalf("digest %q", d)
	}
	if d := contextDigest([]byte("")); d != "" {
		t.Fatalf("digest of nothing %q", d)
	}
	if got := tailLines("a\nb\r\n\nc\n", 2); strings.Join(got, ",") != "b,c" {
		t.Fatalf("tailLines %v", got)
	}
}

func TestUpsAnswerCarriesSliceOnesFields(t *testing.T) {
	f := envFixture(t, "/w")
	body := map[string]any{}
	f.b.slice1Body(body, "compose", map[string]string{"container": "c1"}, nil, nil, nil)
	if body["kind"] != "compose" || body["built"] == nil || body["lifecycle"] == nil || body["not_run"] != nil {
		t.Fatalf("body %v", body)
	}
}
