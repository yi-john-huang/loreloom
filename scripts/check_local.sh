#!/usr/bin/env bash
# Local verification for Loreloom. There is no GitHub Actions; run this before every push.
#
#   scripts/check_local.sh                 run every gate
#   scripts/check_local.sh --portability   also run the Python 3.11 and 3.13 core gates
#   scripts/check_local.sh --help          show this text
#
# Gates: uv sync, doctor, validate daily, validate strict, lint_wiki, full unittest suite.
# Every gate blocks. Strict validation is a gate, as it was in the removed CI.
# The script never changes your Git remotes, config, index, or tracked files.
# --portability runs on this machine's OS only. Run it on macOS and on Windows
# (Git Bash or WSL) to cover those legs of the old CI matrix.
# If a --portability run is interrupted, the next `uv run --locked` re-syncs .venv.
#
# Exit status: 0 all gates passed, 1 a gate failed, 2 usage or missing tool (no gate ran).
set -uo pipefail

# A pre-push hook or a linked worktree can leak these into this process. Test
# fixtures would then write into the real repository. Unset them before any git call.
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_PREFIX || true

self="${BASH_SOURCE[0]}"

usage() {
  sed -n '2,15p' "$self" | sed 's/^# \{0,1\}//'
}

PORTABILITY=0
for arg in "$@"; do
  case "$arg" in
    --portability) PORTABILITY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

for tool in uv git; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool is required" >&2
    exit 2
  fi
done

script_dir="$(cd -P -- "$(dirname -- "$self")" && pwd)" || exit 2
if ! root="$(cd -P -- "$script_dir" && git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "not inside a Git work tree: $script_dir" >&2
  exit 2
fi
cd -P -- "$root" || exit 2

failed=""

record_failure() {
  if [ -z "$failed" ]; then failed="$1"; else failed="$failed; $1"; fi
}

# run_gate NAME COMMAND...  Output streams to the terminal. A failure is recorded, never skipped.
run_gate() {
  local name="$1"; shift
  echo "==> [gate] $name"
  if "$@"; then
    echo "    PASS: $name"
  else
    echo "    FAIL: $name"
    record_failure "$name"
  fi
}

finish() {
  echo
  if [ -n "$failed" ]; then
    echo "Local checks FAILED: $failed"
    exit 1
  fi
  echo "Local checks passed."
  exit 0
}

# Decide with the doctor's own URL parser, so this script and the doctor cannot disagree.
# Python exit 10 = public framework, 11 = another remote. Anything else is an error.
classify_origin() {
  local url rc
  if ! url="$(git remote get-url origin 2>/dev/null)"; then
    echo absent
    return 0
  fi
  uv run --locked python -I -c '
import sys
sys.path.insert(0, sys.argv[1])
from doctor_vault import PUBLIC_FRAMEWORK, normalize_github_remote
sys.exit(10 if normalize_github_remote(sys.argv[2]) == PUBLIC_FRAMEWORK else 11)
' "$root/scripts" "$url" >/dev/null 2>&1
  rc=$?
  case "$rc" in
    10) echo public ;;
    11) echo other ;;
    *) echo error ;;
  esac
}

# The doctor functions take an optional Python version, used by --portability.
run_doctor_in_place() {
  local py="${1:-}"
  if [ -n "$py" ]; then
    uv run --locked --python "$py" python scripts/doctor_vault.py
  else
    uv run --locked python scripts/doctor_vault.py
  fi
}

snap_dir=""

# Remove the doctor snapshot. rm -rf runs only on a directory this script made: it must sit
# directly under the resolved temp root and carry the loreloom-doctor. prefix.
cleanup() {
  local root_tmp
  [ -n "$snap_dir" ] || return 0
  if [ "${CHECK_LOCAL_KEEP_SNAPSHOT:-0}" = 1 ]; then return 0; fi
  root_tmp="$(cd -P -- "${TMPDIR:-/tmp}" 2>/dev/null && pwd)" || root_tmp=""
  case "$snap_dir" in
    "$root_tmp"/loreloom-doctor.*)
      rm -rf -- "$snap_dir"
      if [ -e "$snap_dir" ]; then
        echo "could not remove temporary directory: $snap_dir" >&2
      fi
      ;;
  esac
  snap_dir=""
}

trap cleanup EXIT
trap 'cleanup; trap - INT; kill -INT $$' INT
trap 'cleanup; exit 143' TERM

# Copy the working tree (tracked plus untracked, not ignored) into a throwaway Git
# repo that has no remote and no commit. The user's repository is only read.
build_snapshot() {
  local tmp f
  if ! tmp="$(mktemp -d "${TMPDIR:-/tmp}/loreloom-doctor.XXXXXX")"; then
    echo "could not create temporary directory" >&2
    return 1
  fi
  snap_dir="$(cd -P -- "$tmp" && pwd)" || return 1
  git ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' f; do
    if [ -L "$f" ] || [ -f "$f" ]; then
      mkdir -p -- "$snap_dir/$(dirname -- "$f")" && cp -pP -- "$f" "$snap_dir/$f" || exit 1
    fi
  done
  [ "${PIPESTATUS[1]}" -eq 0 ] || { echo "could not copy the working tree" >&2; return 1; }
  git -C "$snap_dir" -c init.defaultBranch=main init -q || return 1
  # Index the tracked files that still exist, so `git check-ignore` answers as it does here.
  git ls-files -z --cached | while IFS= read -r -d '' f; do
    if [ -L "$f" ] || [ -f "$f" ]; then printf '%s\0' "$f"; fi
  done | git -C "$snap_dir" add -f --pathspec-from-file=- --pathspec-file-nul \
    || { echo "could not index the working-tree copy" >&2; return 1; }
}

# The doctor FAILs remote-privacy while origin is the public framework. The removed CI
# deleted origin first. This script must not touch remotes, so it runs the doctor in
# a copy that has none.
run_doctor_isolated() {
  local py="${1:-}" url rc
  url="$(git remote get-url origin)"
  echo "    NOTE: origin is the public Loreloom framework ($url)."
  echo "    NOTE: the doctor ran in a temporary copy without origin, so remote-privacy was not evaluated in place."
  echo "    NOTE: a private vault must not use the public framework as origin."
  if ! build_snapshot; then
    cleanup
    return 1
  fi
  if [ -n "$py" ]; then
    (cd "$snap_dir" && uv run --locked --project "$root" --python "$py" python scripts/doctor_vault.py)
  else
    (cd "$snap_dir" && uv run --locked --project "$root" python scripts/doctor_vault.py)
  fi
  rc=$?
  if [ "${CHECK_LOCAL_KEEP_SNAPSHOT:-0}" = 1 ]; then echo "    SNAPSHOT: $snap_dir"; fi
  cleanup
  return "$rc"
}

run_doctor() {
  local py="${1:-}"
  case "$(classify_origin)" in
    error)
      echo "could not classify origin URL" >&2
      return 1
      ;;
    public) run_doctor_isolated "$py" ;;
    *) run_doctor_in_place "$py" ;;
  esac
}

run_default_gates() {
  # The sync gate is fatal: every other gate needs the locked environment.
  run_gate "uv sync --locked --dev" uv sync --locked --dev --quiet
  if [ -n "$failed" ]; then finish; fi

  run_gate "doctor_vault" run_doctor
  run_gate "validate_vault --mode daily" uv run --locked python scripts/validate_vault.py --mode daily
  run_gate "validate_vault --mode strict" uv run --locked python scripts/validate_vault.py --mode strict
  run_gate "lint_wiki" uv run --locked python scripts/lint_wiki.py
  run_gate "unittest (full suite)" uv run --locked python -m unittest discover -s tests
}

# The removed CI ran these on Python 3.11 and 3.13 (fail-fast: false), so no gate stops the loop.
run_portability() {
  local py
  for py in 3.11 3.13; do
    run_gate "portability py$py: doctor_vault" run_doctor "$py"
    run_gate "portability py$py: validate daily" uv run --locked --python "$py" python scripts/validate_vault.py --mode daily
    run_gate "portability py$py: validate strict" uv run --locked --python "$py" python scripts/validate_vault.py --mode strict
    run_gate "portability py$py: portable tests" uv run --locked --python "$py" python -m unittest tests.test_doctor_vault tests.test_validate_vault tests.test_jev_advisory tests.test_lightweight_flow
  done
  # Switching interpreters rebuilt .venv. Restore the .python-version environment.
  run_gate "restore default environment" uv sync --locked --dev --quiet
}

# Tests source this file to call the functions above without running any gate.
if [ "${CHECK_LOCAL_SOURCE_ONLY:-0}" = 1 ]; then
  return 0 2>/dev/null || exit 0
fi

run_default_gates
if [ "$PORTABILITY" = 1 ]; then run_portability; fi
finish
