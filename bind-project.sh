#!/bin/sh
# Bind a project to this Lean Harness checkout. The binding only references
# the checkout; it never copies policy, skills, continuity or Git rules.
# Requires Linux coreutils with mktemp -d, mv -T -n and ln -T.
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
must contain no modified, untracked or ignored files. Existing files are
never overwritten, and a run that fails removes what it created.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

# True when $1 exists, including as a dangling symlink.
exists() {
    [ -e "$1" ] || [ -L "$1" ]
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
project_root=$(CDPATH='' cd -- "${project_arg:-.}" && pwd -P) ||
    die "project directory not found: ${project_arg:-.}"
release_commit=$(git -C "$release_root" rev-parse --verify "HEAD^{commit}") ||
    die "$release_root is not a Git checkout"

if [ "$dev" = true ]; then
    release_label="dev-$(printf '%s' "$release_commit" | cut -c1-12)"
else
    release_label=$(git -C "$release_root" describe --tags --exact-match 2>/dev/null) ||
        die "Lean Harness checkout is not at an exact release tag; check out a release or pass --dev"
    command -v gh >/dev/null 2>&1 || die "gh is required to verify release $release_label"
    release_body=$(gh release view "$release_label" --repo "$REPOSITORY" --json body --jq .body) ||
        die "cannot read GitHub release $release_label"
    expected_commit=$(printf '%s\n' "$release_body" | sed -n 's/^Release commit: \([0-9a-f]\{40\}\)$/\1/p')
    if [ "$expected_commit" != "$release_commit" ]; then
        die "release notes of $release_label do not record this checkout's commit $release_commit"
    fi
    release_status=$(git -C "$release_root" status --porcelain --untracked-files=all --ignored=matching) ||
        die "cannot read the status of the release checkout"
    if [ -n "$release_status" ]; then
        die "release checkout contains modified, untracked or ignored files"
    fi
fi

# Names of the Harness skills linked for Claude Code.
skill_names() {
    for skill in "$release_root"/skills/*/; do
        name=$(basename "$skill")
        if [ -d "$skill" ] && [ "$name" != _shared ]; then
            printf '%s\n' "$name"
        fi
    done
}

# Refuse before writing anything.
if [ "$want_omp" = true ] && exists "$project_root/.omp"; then
    die "$project_root/.omp already exists; merge the Harness binding into it by hand"
fi
if [ "$want_claude" = true ]; then
    if exists "$project_root/CLAUDE.md"; then
        die "$project_root/CLAUDE.md already exists; add the line @$release_root/.omp/AGENTS.md to it by hand"
    fi
    for dir in "$project_root/.claude" "$project_root/.claude/skills"; do
        if exists "$dir" && [ ! -d "$dir" ]; then
            die "$dir exists and is not a directory"
        fi
    done
    for name in $(skill_names); do
        if exists "$project_root/.claude/skills/$name"; then
            die "$project_root/.claude/skills/$name already exists"
        fi
    done
fi

# Everything below is staged first, then moved into place. Whatever this run
# created is removed again unless the run completes.
staging=
completed=false
created_omp=false
created_claude_md=false
created_claude_dir=false
created_skills_dir=false
created_links=

cleanup() {
    if [ -n "$staging" ]; then rm -rf -- "$staging" || :; fi
    if [ "$completed" = true ]; then return 0; fi
    if [ "$created_omp" = true ]; then rm -rf -- "$project_root/.omp" || :; fi
    if [ "$created_claude_md" = true ]; then rm -f -- "$project_root/CLAUDE.md" || :; fi
    for name in $created_links; do
        rm -f -- "$project_root/.claude/skills/$name" || :
    done
    if [ "$created_skills_dir" = true ]; then rmdir -- "$project_root/.claude/skills" 2>/dev/null || :; fi
    if [ "$created_claude_dir" = true ]; then rmdir -- "$project_root/.claude" 2>/dev/null || :; fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# Move a staged file or directory to $2 unless something already exists there.
publish() {
    if mv -T -n -- "$1" "$2" && ! exists "$1"; then
        return 0
    fi
    die "$2 appeared while binding; left it untouched"
}

staging=$(mktemp -d "$project_root/.lean-harness-bind.XXXXXX") ||
    die "cannot create a staging directory in $project_root"

header="Lean Harness root: \`$release_root\`.
Lean Harness release: \`$release_label\` at \`$release_commit\`."
footer="## This project

Read this project's README and existing repository documentation for project-specific context."

if [ "$want_omp" = true ]; then
    escaped_root=$(printf '%s' "$release_root" | sed 's/\\/\\\\/g; s/"/\\"/g')
    mkdir "$staging/omp"
    cat >"$staging/omp/config.yml" <<EOF
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
    cat >"$staging/omp/AGENTS.md" <<EOF
# Project context

$header

@$release_root/.omp/AGENTS.md

$footer
EOF
    # OMP reads MCP servers only from the project's .omp/, so this one file is copied.
    cp -- "$release_root/.omp/mcp.json" "$staging/omp/mcp.json"
fi

if [ "$want_claude" = true ]; then
    cat >"$staging/CLAUDE.md" <<EOF
# Project context

$header
Harness skills are linked into \`.claude/skills/\`.

@$release_root/.omp/AGENTS.md

$footer
EOF
fi

if [ "$want_omp" = true ]; then
    publish "$staging/omp" "$project_root/.omp"
    created_omp=true
    printf 'Bound OMP: %s/.omp\n' "$project_root"
fi

if [ "$want_claude" = true ]; then
    if ! exists "$project_root/.claude"; then
        mkdir -- "$project_root/.claude"
        created_claude_dir=true
    fi
    if ! exists "$project_root/.claude/skills"; then
        mkdir -- "$project_root/.claude/skills"
        created_skills_dir=true
    fi
    for name in $(skill_names); do
        # -T: fail instead of creating the link inside a directory that appeared meanwhile.
        ln -s -T -- "$release_root/skills/$name" "$project_root/.claude/skills/$name"
        created_links="$created_links $name"
    done
    publish "$staging/CLAUDE.md" "$project_root/CLAUDE.md"
    created_claude_md=true
    printf 'Bound Claude Code: %s/CLAUDE.md and %s/.claude/skills\n' "$project_root" "$project_root"
fi

completed=true
printf 'Lean Harness %s (%s) bound to %s\n' "$release_label" "$release_commit" "$project_root"
