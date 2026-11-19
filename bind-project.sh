#!/bin/sh
# Bind a project to this Lean Harness checkout. The binding only references
# the checkout; it never copies policy, skills, continuity or Git rules.
# Requires Linux with GNU coreutils (mv -T -n).
set -eu

REPOSITORY="114August514/lean-harness"

usage() {
    cat <<'EOF'
Usage: bind-project.sh [PROJECT_DIR] [--runtime omp|claude|all] [--dev]

Bind PROJECT_DIR (default: current directory) to this Lean Harness checkout.

  --runtime omp     write .omp/{config.yml,AGENTS.md,mcp.json} (default)
  --runtime claude  write CLAUDE.md that imports the Harness entry and link
                    the Harness skills into .claude/skills/
  --runtime all     both
  --dev             bind a development checkout: skip the exact-tag, GitHub
                    release and clean-checkout verification

Without --dev the checkout must sit on an exact release tag whose GitHub
release notes contain "Release commit: <full sha>" for that commit, and it
must contain no modified, untracked or ignored files. Existing bindings are
never overwritten.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

runtime=omp
dev=false
project_arg=
while [ $# -gt 0 ]; do
    case "$1" in
        --runtime)
            [ $# -ge 2 ] || die "--runtime needs a value"
            runtime=$2
            shift 2
            ;;
        --dev)
            dev=true
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        -*)
            die "unknown option: $1"
            ;;
        *)
            [ -z "$project_arg" ] || die "more than one project directory given"
            project_arg=$1
            shift
            ;;
    esac
done

want_omp=false
want_claude=false
case "$runtime" in
    omp) want_omp=true ;;
    claude) want_claude=true ;;
    all)
        want_omp=true
        want_claude=true
        ;;
    *) die "unknown runtime: $runtime (expected omp, claude or all)" ;;
esac

release_root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
project_root=$(CDPATH='' cd -- "${project_arg:-.}" && pwd -P)
release_commit=$(git -C "$release_root" rev-parse --verify "HEAD^{commit}")

if [ "$dev" = true ]; then
    release_label="dev-$(printf '%s' "$release_commit" | cut -c1-12)"
else
    release_label=$(git -C "$release_root" describe --tags --exact-match 2>/dev/null) ||
        die "Lean Harness checkout is not at an exact release tag; check out a release or pass --dev"
    command -v gh >/dev/null 2>&1 || die "gh is required to verify release $release_label"
    release_body=$(gh release view "$release_label" --repo "$REPOSITORY" --json body --jq .body) ||
        die "cannot read GitHub release $release_label"
    expected_commit=$(printf '%s\n' "$release_body" | sed -n 's/^Release commit: \([0-9a-f]\{40\}\)$/\1/p')
    [ "$expected_commit" = "$release_commit" ] ||
        die "release notes of $release_label do not record this checkout's commit $release_commit"
    [ -z "$(git -C "$release_root" status --porcelain --untracked-files=all --ignored=matching)" ] ||
        die "release checkout contains modified, untracked or ignored files"
fi

# Refuse before writing anything.
if [ "$want_omp" = true ] && [ -e "$project_root/.omp" ]; then
    die "$project_root/.omp already exists; merge the Harness binding into it by hand"
fi
if [ "$want_claude" = true ]; then
    if [ -e "$project_root/CLAUDE.md" ]; then
        die "$project_root/CLAUDE.md already exists; add the line @$release_root/.omp/AGENTS.md to it by hand"
    fi
    for skill in "$release_root"/skills/*/; do
        name=$(basename "$skill")
        if [ "$name" = _shared ]; then
            continue
        fi
        if [ -e "$project_root/.claude/skills/$name" ] || [ -L "$project_root/.claude/skills/$name" ]; then
            die "$project_root/.claude/skills/$name already exists"
        fi
    done
fi

header="Lean Harness root: \`$release_root\`.
Lean Harness release: \`$release_label\` at \`$release_commit\`."
footer="## This project

Read this project's README and existing repository documentation for project-specific context."

publish_omp() {
    escaped_root=$(printf '%s' "$release_root" | sed 's/\\/\\\\/g; s/"/\\"/g')
    temporary_dir="$project_root/.omp.lean-harness.$$"
    mkdir "$temporary_dir" || die "cannot create $temporary_dir"
    trap 'rm -rf -- "$temporary_dir"' EXIT HUP INT TERM

    cat >"$temporary_dir/config.yml" <<EOF
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

    cat >"$temporary_dir/AGENTS.md" <<EOF
# Project context

$header

@$release_root/.omp/AGENTS.md

$footer
EOF

    # OMP reads MCP servers only from the project's .omp/, so this one file is copied.
    cp "$release_root/.omp/mcp.json" "$temporary_dir/mcp.json"

    mv -T -n -- "$temporary_dir" "$project_root/.omp" || die "cannot publish $project_root/.omp"
    [ ! -e "$temporary_dir" ] || die "$project_root/.omp was created concurrently; left it untouched"
    trap - EXIT HUP INT TERM
    printf 'Bound OMP: %s/.omp\n' "$project_root"
}

publish_claude() {
    mkdir -p "$project_root/.claude/skills"
    for skill in "$release_root"/skills/*/; do
        name=$(basename "$skill")
        if [ "$name" = _shared ]; then
            continue
        fi
        ln -s -- "${skill%/}" "$project_root/.claude/skills/$name"
    done
    (
        set -C
        cat >"$project_root/CLAUDE.md" <<EOF
# Project context

$header
Harness skills are linked into \`.claude/skills/\`.

@$release_root/.omp/AGENTS.md

$footer
EOF
    ) || die "cannot create $project_root/CLAUDE.md"
    printf 'Bound Claude Code: %s/CLAUDE.md and %s/.claude/skills\n' "$project_root" "$project_root"
}

if [ "$want_omp" = true ]; then
    publish_omp
fi
if [ "$want_claude" = true ]; then
    publish_claude
fi
printf 'Lean Harness %s (%s) bound to %s\n' "$release_label" "$release_commit" "$project_root"
