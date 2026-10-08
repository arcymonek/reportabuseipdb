#!/bin/bash
# Maintainer tool: do the local main, Forgejo ("origin") and GitHub ("github") stand on the same commit?
#   tools/deploy-check.sh [--no-fetch]
# Run it in your clone after a push or a deployment (docs/DEVELOPMENT.md, "Deploying"). It only READS: it fetches the
# remotes (which updates your remote-tracking branches, never your files or branches) and compares commits. It does not
# touch the server; on the server run `git log -1 --format=%h` in the install directory and compare by eye.
# Between the push to origin and the push to github the two remotes DIFFER on purpose (origin first, deploy, github last),
# so a remote that is simply behind is reported as "not pushed yet", not as a failure of the repository.
#   --no-fetch   compare with what the last fetch saw (offline)
# Environment: BRANCH (default main), REMOTES (default "origin github"; the first one must always be pushed first).
# Exit status: 0 everything is the same, 1 something differs (read the lines above it), 2 the check could not run.
# Remote addresses are never printed (git's own error text names them, so it is hidden): the output is safe to paste.
set -u
branch="${BRANCH:-main}"
remotes="${REMOTES:-origin github}"
fetch=1
usage() { echo "usage: tools/deploy-check.sh [--no-fetch]" >&2; }
case "${1:-}" in
    "") ;;
    --no-fetch) fetch=0 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
esac
[ "$#" -le 1 ] || { usage; exit 2; }

fail() { echo "error: $*" >&2; exit 2; }
git rev-parse --git-dir > /dev/null 2>&1 || fail "not inside a git repository"
git rev-parse --verify --quiet "refs/heads/$branch" > /dev/null || fail "there is no local branch '$branch'"

status=0
short="$(git rev-parse --short "$branch")"
printf '%-16s %s\n' "$branch" "$short"
first=""
for r in $remotes; do
    git remote get-url "$r" > /dev/null 2>&1 || fail "there is no remote named '$r' in this repository"
    if [ "$fetch" = 1 ] && ! git fetch --quiet "$r" > /dev/null 2>&1; then
        fail "'git fetch $r' failed (run it by hand to see why; its message is hidden because it contains the remote address)"
    fi
    git rev-parse --verify --quiet "refs/remotes/$r/$branch" > /dev/null || fail "$r/$branch is not known locally (fetch it first)"
    # left = commits only in the local branch, right = commits only in the remote branch
    counts="$(git rev-list --left-right --count "$branch...$r/$branch")"
    ahead="${counts%%[[:space:]]*}"
    behind="${counts##*[[:space:]]}"
    label="$r/$branch"
    if [ "$ahead" = 0 ] && [ "$behind" = 0 ]; then
        printf '%-16s %s  same\n' "$label" "$(git rev-parse --short "$label")"
    elif [ "$behind" = 0 ]; then
        printf '%-16s %s  NOT PUSHED YET: %s is behind %s by %s commit(s)\n' "$label" "$(git rev-parse --short "$label")" "$r" "$branch" "$ahead"
        status=1
    elif [ "$ahead" = 0 ]; then
        printf '%-16s %s  AHEAD: %s has %s commit(s) you do not have (a merge made on a web page?); fetch and look before anything else\n' \
            "$label" "$(git rev-parse --short "$label")" "$r" "$behind"
        status=1
    else
        printf '%-16s %s  DIVERGED: %s has %s commit(s) you lack and you have %s it lacks (rewritten history or a force-push); STOP and ask before fixing anything\n' \
            "$label" "$(git rev-parse --short "$label")" "$r" "$behind" "$ahead"
        status=1
    fi
    if [ -z "$first" ]; then
        first="$r"
    else
        extra="$(git rev-list --count "$first/$branch..$r/$branch")"
        if [ "$extra" != 0 ]; then
            echo "WARNING: $r/$branch has $extra commit(s) that $first/$branch lacks; the order is $first first, then $r"
            status=1
        fi
    fi
done

# Information only, these do not change the exit status.
current="$(git symbolic-ref --short -q HEAD || echo "(detached HEAD)")"
[ "$current" = "$branch" ] || echo "note: you are on '$current', not on '$branch' (the check compares the branch '$branch')"
[ -z "$(git status --porcelain 2> /dev/null)" ] || echo "note: the working tree has uncommitted changes (they are not part of this check)"

echo "Server: after 'git pull --ff-only', 'git log -1 --format=%h' in the install directory should print $short."
if [ "$status" = 0 ]; then echo "RESULT: everything is the same."; else echo "RESULT: something differs, see above."; fi
exit "$status"
