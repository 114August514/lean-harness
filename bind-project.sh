#!/bin/sh
# Bind a project to this Lean Harness checkout. The binding only references
# the checkout; it never copies policy, skills, continuity or Git rules.
# Requires Linux coreutils: mktemp -d, mv -T -n and stat -c.
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
never overwritten. A run that fails or is interrupted deletes what it
published, but only objects that are provably the ones it created and are
unchanged; anything else is kept and reported.
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

# Signals are recorded and acted on only at checkpoints, so everything the
# run publishes is registered before cleanup can run.
signal_status=
trap 'signal_status=129' HUP
trap 'signal_status=130' INT
trap 'signal_status=143' TERM
checkpoint() {
    if [ -n "$signal_status" ]; then
        exit "$signal_status"
    fi
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
checkpoint

# Every object of the binding is staged in a private directory under the
# project root and renamed into place one at a time. The identity (device and
# inode) of each staged object is recorded first, and renaming keeps it.
# Unless the run completes, cleanup deletes a published object only while it
# still has that identity and, for files, the staged content, so it never
# deletes what another writer created or changed.
staging=
completed=false
published=
link_names=
kept=

identity() {
    stat -c '%d:%i' -- "$1" 2>/dev/null || :
}
# record LABEL PATH: remember the identity of staged object PATH.
record() {
    identity "$2" >"$staging/id.$1"
}
# is_ours LABEL PATH: PATH is still the object recorded under LABEL.
is_ours() {
    current=$(identity "$2")
    [ -n "$current" ] && [ "$current" = "$(cat "$staging/id.$1" 2>/dev/null)" ]
}
destination() {
    case "$1" in
        omp) printf '%s\n' "$project_root/.omp" ;;
        claude) printf '%s\n' "$project_root/.claude" ;;
        skills) printf '%s\n' "$project_root/.claude/skills" ;;
        link.*) printf '%s\n' "$project_root/.claude/skills/${1#link.}" ;;
        claudemd) printf '%s\n' "$project_root/CLAUDE.md" ;;
    esac
}
keep() {
    kept="$kept $1"
}
# remove_file LABEL PATH ORIGINAL
remove_file() {
    if is_ours "$1" "$2" && cmp -s "$3" "$2"; then
        rm -f -- "$2" || :
    elif exists "$2"; then
        keep "$2"
    fi
}
# remove_dir LABEL PATH: rmdir only, so a directory with content survives.
remove_dir() {
    if ! exists "$2"; then
        return 0
    fi
    if is_ours "$1" "$2"; then
        rmdir -- "$2" 2>/dev/null || keep "$2"
    else
        keep "$2"
    fi
}

undo() {
    for label in $published; do
        path=$(destination "$label")
        case "$label" in
            omp)
                if is_ours omp "$path"; then
                    for file in config.yml AGENTS.md mcp.json; do
                        remove_file "omp.$file" "$path/$file" "$staging/omp.orig/$file"
                    done
                fi
                remove_dir omp "$path"
                ;;
            claude | skills)
                remove_dir "$label" "$path"
                ;;
            link.*)
                if is_ours "$label" "$path"; then
                    rm -f -- "$path" || :
                elif exists "$path"; then
                    keep "$path"
                fi
                ;;
            claudemd)
                remove_file claudemd "$path" "$staging/CLAUDE.md.orig"
                ;;
        esac
    done
    if [ -n "$kept" ]; then
        printf 'error: left in place because it may not be exactly what this run created:%s\n' "$kept" >&2
    fi
}

cleanup() {
    if [ "$completed" != true ] && [ -n "$staging" ]; then
        undo
    fi
    if [ -n "$staging" ]; then
        rm -rf -- "$staging" || :
    fi
}
trap cleanup EXIT

# publish LABEL STAGED: rename STAGED to the destination of LABEL unless
# something exists there. The label is registered whenever the object has
# arrived, even if mv itself reported a failure afterwards.
publish() {
    target=$(destination "$1")
    mv -T -n -- "$2" "$target" || :
    if exists "$2" || ! exists "$target"; then
        die "cannot publish $target: it appeared meanwhile or could not be written"
    fi
    published="$1 $published"
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
    cp -R -- "$staging/omp" "$staging/omp.orig"
    record omp "$staging/omp"
    for file in config.yml AGENTS.md mcp.json; do
        record "omp.$file" "$staging/omp/$file"
    done
fi

if [ "$want_claude" = true ]; then
    cat >"$staging/CLAUDE.md" <<EOF
# Project context

$header
Harness skills are linked into \`.claude/skills/\`.

@$release_root/.omp/AGENTS.md

$footer
EOF
    cp -- "$staging/CLAUDE.md" "$staging/CLAUDE.md.orig"
    record claudemd "$staging/CLAUDE.md"
    mkdir "$staging/claude" "$staging/skills" "$staging/links"
    record claude "$staging/claude"
    record skills "$staging/skills"
    for name in $(skill_names); do
        ln -s -- "$release_root/skills/$name" "$staging/links/$name"
        record "link.$name" "$staging/links/$name"
        link_names="$link_names $name"
    done
fi
checkpoint

if [ "$want_omp" = true ]; then
    publish omp "$staging/omp"
    checkpoint
fi
if [ "$want_claude" = true ]; then
    if ! exists "$project_root/.claude"; then
        publish claude "$staging/claude"
        checkpoint
    fi
    if ! exists "$project_root/.claude/skills"; then
        publish skills "$staging/skills"
        checkpoint
    fi
    for name in $link_names; do
        publish "link.$name" "$staging/links/$name"
        checkpoint
    done
    publish claudemd "$staging/CLAUDE.md"
    checkpoint
fi
completed=true

if [ "$want_omp" = true ]; then
    printf 'Bound OMP: %s/.omp\n' "$project_root"
fi
if [ "$want_claude" = true ]; then
    printf 'Bound Claude Code: %s/CLAUDE.md and %s/.claude/skills\n' "$project_root" "$project_root"
fi
printf 'Lean Harness %s (%s) bound to %s\n' "$release_label" "$release_commit" "$project_root"
