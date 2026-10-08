#!/usr/bin/env bash
# make-project.sh KIND DIR — writes one small test project into DIR (feature 012, research R1).
#
# The projects exist so that `verify`'s parsers are tested against what the REAL runners print about
# them (cross-stack P005): tests/fixtures/verify/record.sh runs each runner on its project and keeps the
# output. Nothing in this file knows how `verify` parses; it only writes code with a known number of
# tests and failures, which the tests count for themselves.
#
#   pytest  app/ (models, orders, cli) and tests/: 412 tests, 3 failing
#           (test_models.py 6/1, test_orders.py 6/2, test_cli.py 400/0). test_orders.py imports
#           app.orders, which imports app.models, so the e2e for `verify changed` uses it too.
#   jest    12 tests in one file, 3 failing
#   vitest  12 tests in one file, 3 failing
#   go      module example.com/calc: 12 tests, 3 failing (Errorf, Fatalf, a failing subtest)
#   cargo   crate calc: 12 unit tests (3 failing) and 2 integration tests (passing)
#   lint    bad.py (ruff F401, mypy return type), bad.ts with tsconfig (tsc), bad.js with an eslint config
set -euo pipefail

kind="${1:?usage: make-project.sh KIND DIR}"
dir="${2:?usage: make-project.sh KIND DIR}"
mkdir -p "${dir}"
cd "${dir}"

pytest_project() {
  mkdir -p app tests
  : >app/__init__.py
  : >conftest.py
  cat >app/models.py <<'EOF'
class Order:
    def __init__(self, prices: list[int]) -> None:
        self.prices = prices

    def total(self) -> int:
        return sum(self.prices)


def round_money(cents: int) -> int:
    return (cents + 50) // 100 * 100
EOF
  cat >app/orders.py <<'EOF'
from app.models import Order, round_money


def checkout(prices: list[int]) -> int:
    if not prices:
        raise ValueError("empty order")
    return round_money(Order(prices).total())
EOF
  cat >app/cli.py <<'EOF'
def double(n: int) -> int:
    return n * 2
EOF
  cat >tests/test_models.py <<'EOF'
from app.models import Order, round_money


def test_total_of_one():
    assert Order([5]).total() == 5


def test_total_of_two():
    assert Order([1, 2]).total() == 3


def test_total_of_none():
    assert Order([]).total() == 0


def test_round_down():
    assert round_money(149) == 100


def test_round_up():
    assert round_money(150) == 200


def test_total_rounds():
    order = Order([1, 2])
    assert order.total() == 4, "1 + 2 should round to 4"
EOF
  cat >tests/test_orders.py <<'EOF'
from app.orders import checkout


def test_checkout_one():
    assert checkout([100]) == 100


def test_checkout_two():
    assert checkout([100, 200]) == 300


def test_checkout_rounds():
    assert checkout([149]) == 100


def test_checkout_rounds_up():
    assert checkout([150]) == 200


def test_checkout_total_is_wrong():
    assert checkout([100, 100]) == 300


def test_checkout_empty():
    assert checkout([]) == 0
EOF
  {
    printf 'from app.cli import double\n'
    local i
    for i in $(seq 1 400); do
      printf '\n\ndef test_double_%03d():\n    assert double(%d) == %d\n' "${i}" "${i}" "$((i * 2))"
    done
  } >tests/test_cli.py
}

js_tests() {
  # $1: the lines that bring test, expect, add and parse into scope
  cat <<EOF
${1}

test('adds one and one', () => { expect(add(1, 1)).toBe(2); });
test('adds two and two', () => { expect(add(2, 2)).toBe(4); });
test('adds negatives', () => { expect(add(-1, -1)).toBe(-2); });
test('adds zero', () => { expect(add(0, 5)).toBe(5); });
test('adds wrongly', () => {
  expect(add(2, 2)).toBe(5);
});
test('parses a number', () => { expect(parse('3')).toEqual({ value: 3 }); });
test('parses another number', () => { expect(parse('7')).toEqual({ value: 7 }); });
test('parses into the wrong shape', () => {
  expect(parse('4')).toEqual({ value: 4, unit: 'cm' });
});
test('parses zero', () => { expect(parse('0')).toEqual({ value: 0 }); });
test('parses a negative', () => { expect(parse('-2')).toEqual({ value: -2 }); });
test('rejects text', () => {
  parse('abc');
});
test('adds large numbers', () => { expect(add(1000, 2000)).toBe(3000); });
EOF
}

js_project() {
  # $1: how math.js exports: cjs (module.exports, for jest) or esm (export, for vitest)
  cat >math.js <<'EOF'
function add(a, b) {
  return a + b;
}

function parse(text) {
  const value = Number(text);
  if (Number.isNaN(value)) {
    throw new Error(`not a number: ${text}`);
  }
  return { value };
}
EOF
  if [ "${1}" = esm ]; then
    printf '\nexport { add, parse };\n' >>math.js
  else
    printf '\nmodule.exports = { add, parse };\n' >>math.js
  fi
}

case "${kind}" in
  pytest)
    pytest_project
    ;;
  jest)
    js_project cjs
    printf '{ "name": "calc-jest", "private": true }\n' >package.json
    js_tests "// jest provides test and expect as globals
const { add, parse } = require('./math');" >math.test.js
    ;;
  vitest)
    js_project esm
    printf '{ "name": "calc-vitest", "private": true, "type": "module" }\n' >package.json
    js_tests "import { test, expect } from 'vitest';
import { add, parse } from './math.js';" >math.test.js
    ;;
  go)
    printf 'module example.com/calc\n\ngo 1.22\n' >go.mod
    cat >calc.go <<'EOF'
package calc

import "strconv"

func Add(a, b int) int { return a + b }

func Parse(s string) (int, error) { return strconv.Atoi(s) }
EOF
    cat >calc_test.go <<'EOF'
package calc

import "testing"

func TestAddOne(t *testing.T)      { check(t, Add(1, 1), 2) }
func TestAddTwo(t *testing.T)      { check(t, Add(2, 2), 4) }
func TestAddNegative(t *testing.T) { check(t, Add(-1, -1), -2) }
func TestAddZero(t *testing.T)     { check(t, Add(0, 5), 5) }

func TestAddWrongly(t *testing.T) {
	if got := Add(2, 2); got != 5 {
		t.Errorf("Add(2, 2) = %d, want 5", got)
	}
}

func TestParseNumber(t *testing.T) {
	n, err := Parse("3")
	if err != nil || n != 3 {
		t.Fatal("Parse(\"3\") failed")
	}
}

func TestParseText(t *testing.T) {
	_, err := Parse("abc")
	if err != nil {
		t.Fatalf("Parse(\"abc\"): %v", err)
	}
}

func TestParseZero(t *testing.T)     { n, _ := Parse("0"); check(t, n, 0) }
func TestParseNegative(t *testing.T) { n, _ := Parse("-2"); check(t, n, -2) }
func TestAddLarge(t *testing.T)      { check(t, Add(1000, 2000), 3000) }

func TestTable(t *testing.T) {
	for _, c := range []struct{ a, b, want int }{{1, 2, 3}, {2, 2, 5}} {
		t.Run(caseName(c.a, c.b), func(t *testing.T) {
			if got := Add(c.a, c.b); got != c.want {
				t.Errorf("Add(%d, %d) = %d, want %d", c.a, c.b, got, c.want)
			}
		})
	}
}

func TestAddCommutes(t *testing.T) { check(t, Add(3, 4), Add(4, 3)) }

func caseName(a, b int) string { return string(rune('0'+a)) + "+" + string(rune('0'+b)) }

func check(t *testing.T, got, want int) {
	t.Helper()
	if got != want {
		t.Errorf("got %d, want %d", got, want)
	}
}
EOF
    ;;
  cargo)
    mkdir -p src tests
    cat >Cargo.toml <<'EOF'
[package]
name = "calc"
version = "0.1.0"
edition = "2021"
EOF
    cat >src/lib.rs <<'EOF'
pub fn add(a: i64, b: i64) -> i64 {
    a + b
}

pub fn parse(s: &str) -> Option<i64> {
    s.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adds_one_and_one() { assert_eq!(add(1, 1), 2); }
    #[test]
    fn adds_two_and_two() { assert_eq!(add(2, 2), 4); }
    #[test]
    fn adds_negatives() { assert_eq!(add(-1, -1), -2); }
    #[test]
    fn adds_zero() { assert_eq!(add(0, 5), 5); }
    #[test]
    fn adds_wrongly() {
        assert_eq!(add(2, 2), 5);
    }
    #[test]
    fn parses_a_number() { assert_eq!(parse("3"), Some(3)); }
    #[test]
    fn parses_text() {
        assert!(parse("abc").is_some(), "abc should parse");
    }
    #[test]
    fn parses_zero() { assert_eq!(parse("0"), Some(0)); }
    #[test]
    fn parses_a_negative() { assert_eq!(parse("-2"), Some(-2)); }
    #[test]
    fn adds_large() { assert_eq!(add(1000, 2000), 3000); }
    #[test]
    fn gives_up() {
        panic!("not implemented yet");
    }
    #[test]
    fn add_commutes() { assert_eq!(add(3, 4), add(4, 3)); }
}
EOF
    cat >tests/integration.rs <<'EOF'
#[test]
fn adds_from_outside() {
    assert_eq!(calc::add(2, 3), 5);
}

#[test]
fn parses_from_outside() {
    assert_eq!(calc::parse("9"), Some(9));
}
EOF
    ;;
  lint)
    cat >bad.py <<'EOF'
import os


def count(items: list[str]) -> int:
    return ",".join(items)
EOF
    cat >bad.ts <<'EOF'
export function count(items: string[]): number {
  return items.join(",");
}
EOF
    printf '{ "compilerOptions": { "strict": true, "noEmit": true }, "files": ["bad.ts"] }\n' >tsconfig.json
    cat >bad.js <<'EOF'
const unused = 1;

function count(items) {
  return items.length;
}

module.exports = { count };
EOF
    cat >eslint.config.js <<'EOF'
module.exports = [{ files: ["**/*.js"], rules: { "no-unused-vars": "error" } }];
EOF
    ;;
  *)
    echo "make-project.sh: unknown kind: ${kind} (pytest, jest, vitest, go, cargo, lint)" >&2
    exit 2
    ;;
esac
