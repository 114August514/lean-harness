#!/bin/sh
set -eu

REPOSITORY="114August514/lean-harness"

release_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
project_root=$(CDPATH= cd -- "${1:-.}" && pwd -P)
binding_dir="$project_root/.omp"

if [ -e "$binding_dir" ]; then
    printf 'error: %s already exists; refusing to overwrite project OMP configuration\n' "$binding_dir" >&2
    exit 1
fi

release_tag=$(git -C "$release_root" describe --tags --exact-match 2>/dev/null) || {
    printf 'error: Lean Harness checkout is not at an exact release tag\n' >&2
    exit 1
}
release_commit=$(git -C "$release_root" rev-parse --verify "HEAD^{commit}")
release_body=$(gh release view "$release_tag" --repo "$REPOSITORY" --json body --jq .body)
expected_commit=$(printf '%s\n' "$release_body" | sed -n 's/^Release commit: \([0-9a-f]\{40\}\)$/\1/p')

if [ "$expected_commit" != "$release_commit" ]; then
    printf 'error: release commit mismatch for %s\n' "$release_tag" >&2
    exit 1
fi

if [ -n "$(git -C "$release_root" status --porcelain --untracked-files=all --ignored=matching)" ]; then
    printf 'error: Lean Harness release checkout contains modified or untracked content\n' >&2
    exit 1
fi

escaped_root=$(printf '%s' "$release_root" | sed 's/\\/\\\\/g; s/"/\\"/g')
if ! mkdir "$binding_dir" 2>/dev/null; then
    printf 'error: %s was created concurrently; refusing to overwrite it\n' "$binding_dir" >&2
    exit 1
fi

binding_complete=false
cleanup_binding() {
    if [ "$binding_complete" = false ]; then
        rm -rf -- "$binding_dir"
    fi
}
trap cleanup_binding EXIT HUP INT TERM

cat >"$binding_dir/config.yml" <<EOF
skills:
  customDirectories:
    - "$escaped_root/skills"

workspace:
  additionalDirectories:
    - "$escaped_root"

memory:
  backend: off

autolearn:
  enabled: false

task:
  isolation:
    mode: none

github:
  enabled: false
EOF

cat >"$binding_dir/AGENTS.md" <<EOF
# Project context

Lean Harness release root: \`$release_root\`.
Lean Harness release: \`$release_tag\` at \`$release_commit\`.

@$release_root/.omp/AGENTS.md

## This project

Read this project's README and existing repository documentation for project-specific context.
EOF

cp "$release_root/.omp/mcp.json" "$binding_dir/mcp.json"
binding_complete=true
trap - EXIT HUP INT TERM

printf 'Bound Lean Harness %s (%s) to %s\n' "$release_tag" "$release_commit" "$project_root"
printf 'Next: run omp from %s\n' "$project_root"
