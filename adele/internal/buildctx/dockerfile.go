package buildctx

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// Scan is what the Dockerfile asks of the daemon (014 research R15, R16).
type Scan struct {
	Bases   []string // every image a FROM, COPY --from or RUN --mount from= names, in order, without repeats
	Stages  []string // stage names, lowercased, in order; "" for an unnamed stage
	Refusal *Refusal // the first thing no grant allows, or nil
}

// The classic builder pulls a missing base whatever `pull` says, so Adele checks every base is on the daemon
// before building. That makes the scan's job to miss none: a base it cannot see is one the daemon may pull.

var directiveRe = regexp.MustCompile(`^#\s*([a-zA-Z][a-zA-Z0-9]*)\s*=\s*(.+?)\s*$`)

// ScanDockerfile reads Dockerfile text: the `# escape=` directive, line continuations, comments, the ARGs before
// the first FROM (the build's args override their defaults), ${VAR}, $VAR, ${VAR:-default} and kin in FROM and
// COPY --from, `FROM [--platform=X] REF [AS NAME]` and `COPY --from=REF`. A REF that is neither an earlier
// stage's name nor its index is an image; "scratch" is none. It refuses a RUN that asks for a build secret, SSH,
// a network other than the default, or the insecure entitlement. A non-empty target must name a stage.
func ScanDockerfile(data []byte, args map[string]string, target string) (Scan, error) {
	var sc Scan
	insts, err := instructions(string(data))
	if err != nil {
		return sc, err
	}
	meta := map[string]string{}  // ARGs before the first FROM
	stage := map[string]string{} // the current stage's ARGs
	seen := map[string]bool{}
	base := func(ref string) {
		if !seen[ref] {
			seen[ref] = true
			sc.Bases = append(sc.Bases, ref)
		}
	}
	isStageName := func(ref string) bool {
		l := strings.ToLower(ref)
		for _, s := range sc.Stages {
			if s != "" && s == l {
				return true
			}
		}
		return false
	}
	// isStage reports whether a --from names an earlier stage, by name or index. An index that is no earlier
	// stage is an error, as it is to the builder.
	isStage := func(ref string) (bool, error) {
		if n, err := strconv.Atoi(ref); err == nil {
			if n < 0 || n >= len(sc.Stages) {
				return false, fmt.Errorf("--from=%d is not an earlier stage's index", n)
			}
			return true, nil
		}
		return isStageName(ref), nil
	}
	refuse := func(setting, value, remedy string) {
		if sc.Refusal == nil {
			sc.Refusal = &Refusal{Setting: setting, Value: value, Remedy: remedy}
		}
	}

	for _, in := range insts {
		words := fields(in.rest)
		switch in.cmd {
		case "ARG":
			for _, w := range words {
				name, def, hasDef := strings.Cut(w, "=")
				def = unquote(def)
				v, given := args[name]
				switch {
				case len(sc.Stages) == 0:
					if !given {
						v = expand(def, meta, in.escape)
					}
					if given || hasDef {
						meta[name] = v
					} else {
						delete(meta, name)
					}
				case given:
					stage[name] = v
				case hasDef:
					stage[name] = expand(def, stage, in.escape)
				default:
					if mv, ok := meta[name]; ok {
						stage[name] = mv // a meta ARG redeclared in the stage takes its value
					}
				}
			}
		case "FROM":
			i := 0
			for i < len(words) && strings.HasPrefix(words[i], "--") {
				i++ // --platform=X
			}
			if i >= len(words) {
				return sc, fmt.Errorf("line %d: FROM names no image", in.line)
			}
			ref := expand(words[i], meta, in.escape)
			name := ""
			if i+2 < len(words) && strings.EqualFold(words[i+1], "AS") {
				name = strings.ToLower(words[i+2])
			}
			if ref == "" {
				return sc, fmt.Errorf("line %d: FROM %s is empty after its args are substituted", in.line, words[i])
			}
			// FROM names an earlier stage by name only; an index there is an image's name.
			if !isStageName(ref) && !strings.EqualFold(ref, "scratch") {
				base(ref)
			}
			sc.Stages = append(sc.Stages, name)
			stage = map[string]string{}
		case "COPY", "ADD", "RUN":
			if len(sc.Stages) == 0 {
				return sc, fmt.Errorf("line %d: %s comes before the first FROM", in.line, in.cmd)
			}
			for _, w := range words {
				if !strings.HasPrefix(w, "--") {
					break
				}
				flag, val, _ := strings.Cut(w[2:], "=")
				flag = strings.ToLower(flag)
				switch {
				case in.cmd == "COPY" && flag == "from":
					ref := expand(val, stage, in.escape)
					if ref == "" {
						return sc, fmt.Errorf("line %d: COPY --from names nothing", in.line)
					}
					st, err := isStage(ref)
					if err != nil {
						return sc, fmt.Errorf("line %d: %v", in.line, err)
					}
					if !st {
						base(ref)
					}
				case in.cmd == "RUN" && flag == "mount":
					opts := mountOpts(val)
					switch strings.ToLower(opts["type"]) {
					case "secret":
						refuse("build secrets", w, "no grant allows a build secret; drop --mount=type=secret from the RUN")
					case "ssh":
						refuse("build ssh", w, "no grant forwards SSH into a build; drop --mount=type=ssh from the RUN")
					}
					if from := expand(opts["from"], stage, in.escape); from != "" {
						if st, err := isStage(from); err != nil {
							return sc, fmt.Errorf("line %d: %v", in.line, err)
						} else if !st {
							base(from)
						}
					}
				case in.cmd == "RUN" && flag == "network":
					if strings.ToLower(val) != "default" {
						refuse("build network", w, "a build has only the default network; drop --network from the RUN")
					}
				case in.cmd == "RUN" && flag == "security":
					if strings.ToLower(val) == "insecure" {
						refuse("build entitlements", w, "no grant allows an insecure build; drop --security=insecure from the RUN")
					}
				}
			}
		default:
			if len(sc.Stages) == 0 {
				return sc, fmt.Errorf("line %d: %s comes before the first FROM; only ARG may", in.line, in.cmd)
			}
		}
	}
	if len(sc.Stages) == 0 {
		return sc, fmt.Errorf("the Dockerfile has no FROM")
	}
	if target != "" {
		found := false
		for _, s := range sc.Stages {
			if s != "" && s == strings.ToLower(target) {
				found = true
			}
		}
		if !found {
			return sc, fmt.Errorf("build.target %q names no stage of the Dockerfile; its stages are %s", target, stageList(sc.Stages))
		}
	}
	return sc, nil
}

func stageList(stages []string) string {
	var named []string
	for _, s := range stages {
		if s != "" {
			named = append(named, s)
		}
	}
	if len(named) == 0 {
		return "unnamed (name one with FROM ... AS NAME)"
	}
	return strings.Join(named, ", ")
}

type instruction struct {
	cmd    string // upper-cased
	rest   string
	line   int // where it starts
	escape byte
}

// instructions splits Dockerfile text into instructions, as the classic builder's parser does: parser directives
// at the very top, comment lines dropped (inside a continuation too), blank lines inside a continuation skipped,
// and a line ending in the escape character joined to the next.
func instructions(text string) ([]instruction, error) {
	escape := byte('\\')
	lines := strings.Split(strings.ReplaceAll(strings.TrimPrefix(text, "\ufeff"), "\r\n", "\n"), "\n")
	i := 0
	for ; i < len(lines); i++ {
		m := directiveRe.FindStringSubmatch(lines[i])
		if m == nil {
			break
		}
		if strings.EqualFold(m[1], "escape") {
			if m[2] != "\\" && m[2] != "`" {
				return nil, fmt.Errorf("line %d: escape must be \\ or `, not %q", i+1, m[2])
			}
			escape = m[2][0]
		}
	}
	var out []instruction
	var cur strings.Builder
	start := 0
	open := false
	for ; i < len(lines); i++ {
		line := lines[i]
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "#") || (trimmed == "" && open) {
			continue
		}
		if trimmed == "" {
			continue
		}
		if !open {
			start = i + 1
			cur.Reset()
		}
		body := strings.TrimRight(line, " \t")
		if body[len(body)-1] == escape {
			cur.WriteString(body[:len(body)-1])
			open = true
			continue
		}
		cur.WriteString(body)
		open = false
		out = append(out, split(cur.String(), start, escape))
	}
	if open && strings.TrimSpace(cur.String()) != "" {
		out = append(out, split(cur.String(), start, escape))
	}
	return out, nil
}

func split(s string, line int, escape byte) instruction {
	s = strings.TrimSpace(s)
	var cmd, rest string
	if j := strings.IndexAny(s, " \t"); j >= 0 {
		cmd, rest = s[:j], s[j+1:]
	} else {
		cmd, rest = s, ""
	}
	return instruction{cmd: strings.ToUpper(cmd), rest: strings.TrimSpace(rest), line: line, escape: escape}
}

// fields splits on white space, keeping a double- or single-quoted run together.
func fields(s string) []string {
	var out []string
	var b strings.Builder
	var quote rune
	in := false
	for _, r := range s {
		switch {
		case quote != 0:
			b.WriteRune(r)
			if r == quote {
				quote = 0
			}
		case r == '"' || r == '\'':
			quote, in = r, true
			b.WriteRune(r)
		case r == ' ' || r == '\t':
			if in {
				out = append(out, b.String())
				b.Reset()
				in = false
			}
		default:
			b.WriteRune(r)
			in = true
		}
	}
	if in {
		out = append(out, b.String())
	}
	return out
}

func unquote(s string) string {
	if len(s) >= 2 && (s[0] == '"' || s[0] == '\'') && s[len(s)-1] == s[0] {
		return s[1 : len(s)-1]
	}
	return s
}

func mountOpts(v string) map[string]string {
	out := map[string]string{}
	for _, kv := range strings.Split(unquote(v), ",") {
		k, val, _ := strings.Cut(strings.TrimSpace(kv), "=")
		out[strings.ToLower(k)] = val
	}
	return out
}

// expand substitutes $VAR, ${VAR}, ${VAR:-word}, ${VAR-word}, ${VAR:+word} and ${VAR+word}; the escape character
// before a '$' keeps it literal. An unset variable is empty, as the builder makes it.
func expand(s string, vars map[string]string, escape byte) string {
	s = unquote(s)
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == escape && i+1 < len(s) && s[i+1] == '$' {
			b.WriteByte('$')
			i++
			continue
		}
		if c != '$' || i+1 >= len(s) {
			b.WriteByte(c)
			continue
		}
		if s[i+1] == '{' {
			end := closing(s[i+2:])
			if end < 0 {
				b.WriteString(s[i:])
				break
			}
			b.WriteString(braced(s[i+2:i+2+end], vars, escape))
			i += 2 + end
			continue
		}
		j := i + 1
		for j < len(s) && (s[j] == '_' || s[j] >= 'a' && s[j] <= 'z' || s[j] >= 'A' && s[j] <= 'Z' || s[j] >= '0' && s[j] <= '9') {
			j++
		}
		if j == i+1 {
			b.WriteByte(c)
			continue
		}
		b.WriteString(vars[s[i+1:j]])
		i = j - 1
	}
	return b.String()
}

// closing finds the '}' that closes a "${", allowing nested ones in a default.
func closing(s string) int {
	depth := 0
	for i := 0; i < len(s); i++ {
		switch {
		case s[i] == '$' && i+1 < len(s) && s[i+1] == '{':
			depth++
			i++
		case s[i] == '}':
			if depth == 0 {
				return i
			}
			depth--
		}
	}
	return -1
}

func braced(inner string, vars map[string]string, escape byte) string {
	for _, op := range []string{":-", ":+", "-", "+"} {
		name, word, ok := strings.Cut(inner, op)
		if !ok || strings.ContainsAny(name, ":-+") {
			continue
		}
		v, set := vars[name]
		switch op {
		case ":-":
			if v == "" {
				return expand(word, vars, escape)
			}
			return v
		case "-":
			if !set {
				return expand(word, vars, escape)
			}
			return v
		case ":+":
			if v != "" {
				return expand(word, vars, escape)
			}
			return ""
		case "+":
			if set {
				return expand(word, vars, escape)
			}
			return ""
		}
	}
	return vars[inner]
}
