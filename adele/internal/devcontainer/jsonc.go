package devcontainer

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
)

// SyntaxError is a devcontainer.json that does not parse. Line is 1-based and counts the original text, comments
// included, because blanking keeps every byte where it was.
type SyntaxError struct {
	Line int
	Msg  string
}

func (e *SyntaxError) Error() string {
	return fmt.Sprintf("devcontainer.json line %d: %s", e.Line, e.Msg)
}

// blank returns data with its comments and trailing commas replaced by spaces of the same length, newlines kept, so
// an offset into the result is an offset into the original (014 research R12). Text inside strings is never
// touched, escapes included: "a\"//b" is one string.
func blank(data []byte) []byte {
	out := bytes.Clone(data)
	const (
		code = iota
		str
		line
		block
	)
	state := code
	for i := 0; i < len(out); i++ {
		c := out[i]
		switch state {
		case str:
			switch c {
			case '\\':
				i++ // the escaped byte is the string's, whatever it is
			case '"':
				state = code
			}
		case line:
			if c == '\n' {
				state = code
			} else {
				out[i] = ' '
			}
		case block:
			if c == '*' && i+1 < len(out) && out[i+1] == '/' {
				out[i], out[i+1] = ' ', ' '
				i++
				state = code
			} else if c != '\n' && c != '\r' {
				out[i] = ' '
			}
		default:
			switch {
			case c == '"':
				state = str
			case c == '/' && i+1 < len(out) && out[i+1] == '/':
				out[i], out[i+1] = ' ', ' '
				i++
				state = line
			case c == '/' && i+1 < len(out) && out[i+1] == '*':
				out[i], out[i+1] = ' ', ' '
				i++
				state = block
			}
		}
	}
	// Comments are spaces now, so a trailing comma is a comma outside a string whose next non-space byte closes.
	inStr := false
	for i := 0; i < len(out); i++ {
		c := out[i]
		if inStr {
			switch c {
			case '\\':
				i++
			case '"':
				inStr = false
			}
			continue
		}
		switch c {
		case '"':
			inStr = true
		case ',':
			j := i + 1
			for j < len(out) && (out[j] == ' ' || out[j] == '\t' || out[j] == '\n' || out[j] == '\r') {
				j++
			}
			if j < len(out) && (out[j] == '}' || out[j] == ']') {
				out[i] = ' '
			}
		}
	}
	return out
}

// lineAt is the 1-based line of the byte the decoder had just read when it stopped (offset counts bytes read).
func lineAt(data []byte, offset int64) int {
	end := int(offset) - 1
	if end > len(data) {
		end = len(data)
	}
	if end < 0 {
		end = 0
	}
	return 1 + bytes.Count(data[:end], []byte{'\n'})
}

// ParseJSONC decodes a devcontainer.json: JSON with comments and trailing commas. Its top level must be an object.
// Every parse failure is a *SyntaxError naming the line in the original text.
func ParseJSONC(data []byte) (map[string]any, error) {
	clean := blank(data)
	var v any
	if err := json.Unmarshal(clean, &v); err != nil {
		var se *json.SyntaxError
		var te *json.UnmarshalTypeError
		switch {
		case errors.As(err, &se):
			return nil, &SyntaxError{Line: lineAt(clean, se.Offset), Msg: se.Error()}
		case errors.As(err, &te):
			return nil, &SyntaxError{Line: lineAt(clean, te.Offset), Msg: te.Error()}
		}
		return nil, &SyntaxError{Line: 1, Msg: err.Error()}
	}
	obj, ok := v.(map[string]any)
	if !ok {
		return nil, &SyntaxError{Line: 1, Msg: "the top level is not an object"}
	}
	return obj, nil
}
