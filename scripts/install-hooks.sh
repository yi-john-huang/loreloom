#!/usr/bin/env bash
# Opt-in: install a Git pre-push hook that runs scripts/check_local.sh before every push.
# Nothing installs this automatically. Run it once per clone:
#
#   scripts/install-hooks.sh            install the hook
#   scripts/install-hooks.sh --force    replace a pre-push hook that this script did not write
#   scripts/install-hooks.sh --help     show this text
#
# Remove the hook:  rm "$(git rev-parse --git-path hooks)/pre-push"
# Skip it once:     git push --no-verify
#
# Exit status: 0 installed, 1 a foreign hook exists (rerun with --force), 2 usage error.
set -euo pipefail

# A hook or a linked worktree can leak these into this process. Unset them before any git call.
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_PREFIX || true

self="${BASH_SOURCE[0]}"
force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -h|--help) sed -n '2,12p' "$self" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

script_dir="$(cd -P -- "$(dirname -- "$self")" && pwd)"
if ! root="$(cd -P -- "$script_dir" && git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "not inside a Git work tree: $script_dir" >&2
  exit 2
fi

hooks_dir="$(git -C "$root" rev-parse --git-path hooks)"
case "$hooks_dir" in /*) ;; *) hooks_dir="$root/$hooks_dir" ;; esac
hook="$hooks_dir/pre-push"
marker="# loreloom-local-checks"

if [ -e "$hook" ] && ! grep -q -- "$marker" "$hook" && [ "$force" -ne 1 ]; then
  echo "A different pre-push hook already exists at $hook; rerun with --force to replace it." >&2
  exit 1
fi

mkdir -p -- "$hooks_dir"
tmp="$hooks_dir/pre-push.tmp.$$"
trap 'rm -f -- "$tmp"' EXIT
cat >"$tmp" <<'HOOK'
#!/usr/bin/env bash
# loreloom-local-checks
# Runs scripts/check_local.sh before every push. There is no GitHub Actions.
# Skip it once with: git push --no-verify
set -euo pipefail
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_PREFIX || true
root="$(git rev-parse --show-toplevel)"
if [ ! -x "$root/scripts/check_local.sh" ]; then
  echo "pre-push: $root/scripts/check_local.sh not found; this branch predates the local checks." >&2
  echo "pre-push: run the checks another way, then push with --no-verify." >&2
  exit 1
fi
exec "$root/scripts/check_local.sh"
HOOK
chmod +x "$tmp"
mv -f -- "$tmp" "$hook"
echo "Installed pre-push hook: $hook"
