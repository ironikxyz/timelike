package compose

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"timelike/adele/internal/engine"
)

const ws = "/w/ws1"

func model(t *testing.T, src string) Model {
	t.Helper()
	var out Model
	if err := json.Unmarshal([]byte(src), &out); err != nil {
		t.Fatalf("bad fixture: %v", err)
	}
	return out
}

// One service, given as JSON fields, inside a model with nothing else.
func svc(t *testing.T, fields string) Model {
	t.Helper()
	sep := ""
	if fields != "" {
		sep = ", "
	}
	return model(t, `{"name": "p", "services": {"db": {"image": "debian:x"`+sep+fields+`}}}`)
}

func TestCheckRefusesEachForbiddenSettingNamingIt(t *testing.T) {
	cases := []struct{ fields, setting string }{
		{`"privileged": true`, "privileged"},
		{`"network_mode": "host"`, "network_mode"},
		{`"network_mode": "container:other"`, "network_mode"},
		{`"pid": "host"`, "pid"},
		{`"pid": "container:x"`, "pid"},
		{`"ipc": "host"`, "ipc"},
		{`"uts": "host"`, "uts"},
		{`"userns_mode": "host"`, "userns_mode"},
		{`"cgroup": "host"`, "cgroup"},
		{`"cap_add": ["NET_ADMIN"]`, "cap_add"},
		{`"devices": [{"source": "/dev/kvm", "target": "/dev/kvm"}]`, "devices"},
		{`"device_cgroup_rules": ["c 1:3 mr"]`, "device_cgroup_rules"},
		{`"gpus": "all"`, "gpus"},
		{`"security_opt": ["seccomp=unconfined"]`, "security_opt"},
		{`"security_opt": ["apparmor=unconfined"]`, "security_opt"},
		{`"runtime": "runc-x"`, "runtime"},
		{`"cgroup_parent": "/x"`, "cgroup_parent"},
		{`"external_links": ["other:db"]`, "external_links"},
		{`"volumes_from": ["container:other"]`, "volumes_from"},
		{`"container_name": "timelike-agent"`, "container_name"},
		{`"build": {"context": "/w/ws1/p"}`, "build"},
		{`"labels": {"xyz.ironik.timelike.env": "spoof"}`, "labels"},
		{`"deploy": {"resources": {"reservations": {"devices": [{"capabilities": ["gpu"]}]}}}`, "deploy.resources.reservations.devices"},
		{`"volumes": [{"type": "bind", "source": "/etc", "target": "/etc"}]`, "volumes"},
		{`"volumes": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}]`, "volumes"},
		{`"volumes": [{"type": "npipe", "source": "x", "target": "/x"}]`, "volumes"},
	}
	for _, c := range cases {
		r := Check(svc(t, c.fields), ws, map[string]string{})
		if r == nil {
			t.Errorf("%s: not refused", c.fields)
			continue
		}
		if r.Setting != c.setting || r.Service != "db" || r.Kind != KindSetting || !r.NoGrant() || r.Remedy == "" {
			t.Errorf("%s: refused as %+v, want setting %s of service db", c.fields, r, c.setting)
		}
	}
}

func TestCheckAllowsAPlainProject(t *testing.T) {
	m := model(t, `{"name": "p", "services": {
	  "db": {"image": "debian:x", "security_opt": ["no-new-privileges:true"], "network_mode": "none",
	         "volumes": [{"type": "bind", "source": "/w/ws1/p", "target": "/w/ws1/p"}, {"type": "volume", "source": "data", "target": "/data"}]},
	  "web": {"image": "debian:x", "pid": "service:db", "expose": ["8080"]}},
	  "volumes": {"data": {"name": "p_data"}}, "networks": {"default": {"name": "p_default"}}, "x-extra": 1}`)
	if r := Check(m, ws, map[string]string{"/w/ws1/p": "/w/ws1/p"}); r != nil {
		t.Fatalf("refused %+v", r)
	}
}

func TestCheckBindSourceMustResolveInsideTheWorkspace(t *testing.T) {
	m := svc(t, `"volumes": [{"type": "bind", "source": "/w/ws1/p/link", "target": "/x"}]`)
	if r := Check(m, ws, map[string]string{"/w/ws1/p/link": "/var/lib/docker/volumes/x/_data"}); r == nil || r.Setting != "volumes" ||
		!strings.Contains(r.Value, "resolves to /var/lib/docker") {
		t.Fatalf("a link out of the workspace: %+v", r)
	}
	if r := Check(m, ws, map[string]string{"/w/ws1/p/link": ""}); r == nil || !strings.Contains(r.Value, "does not resolve") {
		t.Fatalf("an unresolvable source: %+v", r)
	}
	if r := Check(m, ws, map[string]string{}); r == nil {
		t.Fatal("a source the sandbox never resolved is accepted")
	}
	if r := Check(svc(t, `"volumes": [{"type": "bind", "source": "/w/ws10/p", "target": "/x"}]`), ws, map[string]string{"/w/ws10/p": "/w/ws10/p"}); r == nil {
		t.Fatal("a sibling of the workspace with the same prefix is accepted")
	}
}

func TestCheckTopLevelVolumesNetworksSecrets(t *testing.T) {
	cases := []struct{ src, setting string }{
		{`"volumes": {"v": {"driver_opts": {"type": "none", "o": "bind", "device": "/etc"}}}`, "volumes"},
		{`"volumes": {"v": {"external": true}}`, "volumes"},
		{`"volumes": {"v": {"driver": "nfs"}}`, "volumes"},
		{`"networks": {"n": {"external": true}}`, "networks"},
		{`"networks": {"n": {"driver": "macvlan"}}`, "networks"},
		{`"networks": {"n": {"driver_opts": {"a": "b"}}}`, "networks"},
		{`"secrets": {"s": {"file": "/run/adele-secret/canary"}}`, "secrets"},
		{`"configs": {"c": {"file": "/etc/passwd"}}`, "configs"},
		{`"models": {"m": {}}`, "models"},
	}
	for _, c := range cases {
		m := model(t, `{"name": "p", "services": {"db": {"image": "debian:x"}}, `+c.src+`}`)
		if r := Check(m, ws, map[string]string{}); r == nil || r.Setting != c.setting {
			t.Errorf("%s: %+v, want %s", c.src, r, c.setting)
		}
	}
}

func TestBindSourcesListsBindsSecretsAndConfigs(t *testing.T) {
	m := model(t, `{"services": {"a": {"volumes": [{"type": "bind", "source": "/w/ws1/a"}, {"type": "volume", "source": "v"}]},
	  "b": {"volumes": [{"type": "bind", "source": "/w/ws1/a"}]}}, "secrets": {"s": {"file": "/w/ws1/s"}}, "configs": {"c": {"content": "x"}}}`)
	got := strings.Join(BindSources(m), " ")
	if got != "/w/ws1/a /w/ws1/s" {
		t.Fatalf("BindSources = %q", got)
	}
}

func TestPortsPublishedAndContainer(t *testing.T) {
	m := model(t, `{"services": {"web": {"expose": ["8080/tcp", "9000"], "ports": [{"target": 80, "published": "8081"}, {"target": 443}]}}}`)
	if p := Published(m); len(p) != 1 || p[0] != 8081 {
		t.Fatalf("Published = %v", p)
	}
	if p := ContainerPorts(m)["web"]; len(p) != 4 || p[0] != 80 || p[3] != 9000 {
		t.Fatalf("ContainerPorts = %v", p)
	}
}

func TestInjectLabelsEverythingAndJoinsTheSharedNetwork(t *testing.T) {
	m := model(t, `{"name": "orig", "services": {"db": {"image": "debian:x", "env_file": [{"path": "/w/ws1/.env"}], "pull_policy": "always", "expose": ["5432"]},
	  "solo": {"image": "debian:x", "network_mode": "none"}}, "volumes": {"data": {}}}`)
	created := time.Date(2026, 10, 17, 4, 0, 0, 0, time.UTC)
	raw, err := Inject(m, "tl-p-abc123", created, time.Hour, Hash(m))
	if err != nil {
		t.Fatal(err)
	}
	out := model(t, string(raw))
	if out["name"] != "tl-p-abc123" {
		t.Fatalf("name %v", out["name"])
	}
	db := out["services"].(map[string]any)["db"].(map[string]any)
	if _, ok := db["env_file"]; ok {
		t.Fatal("env_file kept")
	}
	if _, ok := db["pull_policy"]; ok {
		t.Fatal("pull_policy kept")
	}
	l := db["labels"].(map[string]any)
	if l[engine.LabelEnv] != "tl-p-abc123" || l[engine.LabelCreated] != "2026-10-17T04:00:00Z" || l[engine.LabelTTL] != "3600" ||
		l[engine.LabelPorts] != "5432" || l[engine.LabelModel] != Hash(m) {
		t.Fatalf("labels %v", l)
	}
	nets := db["networks"].(map[string]any)
	if _, ok := nets["default"]; !ok {
		t.Fatal("the service lost its default network")
	}
	alias := nets[Network].(map[string]any)["aliases"].([]any)
	if alias[0] != "db.tl-p-abc123" {
		t.Fatalf("aliases %v", alias)
	}
	solo := out["services"].(map[string]any)["solo"].(map[string]any)
	if _, ok := solo["networks"]; ok {
		t.Fatal("networks beside network_mode")
	}
	top := out["networks"].(map[string]any)
	if top[Network].(map[string]any)["external"] != true || top["default"].(map[string]any)["labels"].(map[string]any)[engine.LabelEnv] != "tl-p-abc123" {
		t.Fatalf("networks %v", top)
	}
	if out["volumes"].(map[string]any)["data"].(map[string]any)["labels"].(map[string]any)[engine.LabelEnv] != "tl-p-abc123" {
		t.Fatal("volume unlabelled")
	}
	if Hash(m) != Hash(model(t, `{"volumes": {"data": {}}, "services": {"solo": {"network_mode": "none", "image": "debian:x"}, "db": {"pull_policy": "always", "expose": ["5432"], "image": "debian:x", "env_file": [{"path": "/w/ws1/.env"}]}}, "name": "orig"}`)) {
		t.Fatal("the hash depends on key order")
	}
}

func TestNamesAndWithin(t *testing.T) {
	n := DefaultName("/w/ws1/My Project_2")
	if n != "tl-my-project-2-48c3cb" { // the agent's client computes the same (tests/unit/test_adele_env_cli.py)
		t.Fatalf("DefaultName = %q", n)
	}
	if !ValidName(n) || !strings.HasPrefix(n, "tl-my-project-2-") || n == DefaultName("/w/ws2/My Project_2") {
		t.Fatalf("DefaultName = %q", n)
	}
	for _, bad := range []string{"timelike", "tl-", "tl-UP", "tl-a_b", "x-tl-a"} {
		if ValidName(bad) {
			t.Errorf("%q accepted", bad)
		}
	}
	if !Within("/w/ws1", ws) || !Within("/w/ws1/a/../b", ws) || Within("/w/ws1/../x", ws) || Within("rel", ws) {
		t.Fatal("Within")
	}
}

func TestUnsetAndOutside(t *testing.T) {
	stderr := `time="2026" level=warning msg="The \"DB_PASSWORD\" variable is not set. Defaulting to a blank string."` + "\n" +
		`time="2026" level=warning msg="The \"DB_PASSWORD\" variable is not set. Defaulting to a blank string."` + "\n" +
		`The "PORT" variable is not set. Defaulting to a blank string.`
	if u := strings.Join(Unset(stderr), ","); u != "DB_PASSWORD,PORT" {
		t.Fatalf("Unset = %q", u)
	}
	r := Outside(`env file /run/adele-secret/canary not found: stat /run/adele-secret/canary: no such file or directory`, ws)
	if r == nil || r.Setting != "env_file" || r.Value != "/run/adele-secret/canary" || r.Kind != KindFile || !r.NoGrant() {
		t.Fatalf("Outside env_file = %+v", r)
	}
	if r := Outside(`open /etc/x/compose.yaml: no such file or directory (include)`, ws); r == nil || r.Setting != "include" {
		t.Fatalf("Outside include = %+v", r)
	}
	if r := Outside(`services.db.image must be a string (in /w/ws1/p/compose.yaml)`, ws); r != nil {
		t.Fatalf("a project error inside the workspace became %+v", r)
	}
}
