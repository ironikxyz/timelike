package broker

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"timelike/adele/internal/compose"
	"timelike/adele/internal/engine"
	"timelike/adele/internal/ledger"
)

// The docker.compose path past these checks is driven against the real daemon in the e2e lane (tech-stack: Adele's
// Docker calls are never mocked to reach coverage). These units cover what is decided before the daemon is asked.

const envGrants = "[grant env]\ncapabilities = docker.compose\nbudget = 0.00 USD\nttl = 2h\ninstances = 2\nports = none\n"

func envReq(action, name, dir string) Request {
	return Request{Session: "s1", Capability: "docker.compose", Action: action, Params: Params{Name: name, Dir: dir}}
}

func envFixture(t *testing.T, ws string) *fixture {
	f := newFixture(t, envGrants)
	f.b.Envs = &Envs{Engine: engine.New("/nonexistent/docker.sock"), Workspace: ws, HostGit: "enforced"}
	return f
}

func TestEnvRequestsAreRefusedBeforeTheDaemonWhenTheyCannotBeRight(t *testing.T) {
	cases := []struct {
		name   string
		ws     string
		req    Request
		status int
		has    string
	}{
		{"an unknown action", "/w", envReq("create", "tl-p-1", "/w/p"), http.StatusBadRequest, "has no action"},
		{"no workspace mounted", "", envReq("up", "tl-p-1", "/w/p"), http.StatusBadRequest, "no workspace was mounted"},
		{"a name outside tl-", "/w", envReq("up", "timelike-agent", "/w/p"), http.StatusBadRequest, "bad environment name"},
		{"a dir outside the workspace", "/w", envReq("up", "tl-p-1", "/etc"), http.StatusBadRequest, "not inside the workspace"},
		{"a relative dir", "/w", envReq("up", "tl-p-1", "w/p"), http.StatusBadRequest, "not inside the workspace"},
		{"an unclean dir", "/w", envReq("up", "tl-p-1", "/w/p/../../etc"), http.StatusBadRequest, "not inside the workspace"},
	}
	for _, c := range cases {
		f := envFixture(t, c.ws)
		out := f.handle(c.req)
		if out.Status != c.status || !strings.Contains(out.Body["error"].(string), c.has) {
			t.Errorf("%s: %d %v", c.name, out.Status, out.Body)
		}
		if n := len(f.rows(t)); n != 0 {
			t.Errorf("%s: %d ledger rows", c.name, n)
		}
	}
	f := envFixture(t, "/w")
	req := envReq("up", "tl-p-1", "/w/p")
	req.Params.Files = []string{"../../etc/compose.yaml"}
	if out := f.handle(req); out.Status != http.StatusBadRequest {
		t.Errorf("a compose file outside the project: %d", out.Status)
	}
}

func TestNoDaemonIsSaidPlainly(t *testing.T) {
	f := newFixture(t, envGrants)
	out := f.handle(envReq("up", "tl-p-1", "/w/p"))
	if out.Status != http.StatusServiceUnavailable || !strings.Contains(out.Body["error"].(string), "no Docker daemon") {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
}

func TestASettingRefusalNamesNoOperatorCommandAndIsRecorded(t *testing.T) {
	f := envFixture(t, "/w")
	out := f.b.refuseEnv(envReq("up", "tl-p-1", "/w/p"), "env", &compose.Refusal{Kind: compose.KindSetting, Service: "db",
		Setting: "privileged", Value: "true", Remedy: "run it without privileged"})
	if out.Status != http.StatusUnprocessableEntity || out.Body["setting"] != "privileged" || out.Body["operator_command"] != "" ||
		out.Body["remediation"] != "no grant allows it; run it without privileged" || out.Body["performed"] != false {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
	rows := f.rows(t)
	if len(rows) != 1 || rows[0].Outcome != ledger.OutcomeRefused || rows[0].LimitName != "privileged" || rows[0].Extend != "" ||
		rows[0].Host != EnvHost || rows[0].Needed != "service db: true" {
		t.Fatalf("ledger %+v", rows)
	}
}

func TestAMissingImageNamesTheOperatorsPull(t *testing.T) {
	f := envFixture(t, "/w")
	out := f.b.refuseEnv(envReq("up", "tl-p-1", "/w/p"), "env", &compose.Refusal{Kind: compose.KindImage, Service: "db",
		Setting: "image", Value: "debian:none", Remedy: MissingImageRemedy("debian:none")})
	if out.Status != http.StatusUnprocessableEntity || out.Body["refusal"] != "image" || out.Body["operator_command"] != "docker pull debian:none" {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
	if rows := f.rows(t); rows[0].Extend != "docker pull debian:none" {
		t.Fatalf("ledger %+v", rows)
	}
}

func TestEnvListWithoutADaemon(t *testing.T) {
	f := newFixture(t, envGrants)
	if _, err := f.b.EnvList(context.Background()); err == nil {
		t.Fatal("no error")
	}
}

// A failed sandbox's remediation names its cause: make build only for a missing image (lane 13s0a, item A).
func TestASandboxRemedyNamesItsCause(t *testing.T) {
	img := "timelike-adele:local"
	missing := &engine.SandboxError{Phase: "create", Err: &engine.APIError{Status: http.StatusNotFound}}
	if r := SandboxRemedy(missing, img); !strings.Contains(r, "make build") {
		t.Errorf("missing: %s", r)
	}
	slow := &engine.SandboxError{Phase: "wait", TimedOut: true}
	if r := SandboxRemedy(slow, img); strings.Contains(r, "make build") || !strings.Contains(r, "slow") {
		t.Errorf("slow: %s", r)
	}
	if r := SandboxRemedy(&engine.SandboxError{Phase: "start", Err: context.Canceled}, img); strings.Contains(r, "make build") {
		t.Errorf("other: %s", r)
	}
}
