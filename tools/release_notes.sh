#!/bin/bash
# Prints the release notes for one version, taken from CHANGELOG.md (used by .github/workflows/release.yml).
#   tools/release_notes.sh <version> [<previous release version>] [<changelog file>]
# Between two releases the version number rises many times (every change of the program raises it), so an operator
# who updates from the previous release needs the notes of ALL those versions, not only of the last one. With a previous
# version the output holds every "## X.Y.Z - date" entry newer than it, up to and including <version>; without one (the
# first release) only the entry of <version>. The entry of <version> is always printed, so a mistake in the previous
# version can never produce empty notes. "Unreleased", "Development" and the "3.5 and earlier" entry are never included.
set -eu
version="${1:?usage: release_notes.sh <version> [<previous version>] [<changelog>]}"
previous="${2:-}"
changelog="${3:-CHANGELOG.md}"

awk -v target="$version" -v prev="$previous" '
    # "3.6.33" -> a number that sorts like the version (Z may exceed 99, so give each part plenty of room)
    function key(v,   p) { split(v, p, "."); return p[1] * 1e12 + p[2] * 1e6 + p[3] }
    /^## / {
        want = 0
        v = $2
        if (v ~ /^[0-9]+\.[0-9]+\.[0-9]+$/) {
            if (v == target) want = 1
            else if (prev != "" && key(v) > key(prev) && key(v) <= key(target)) want = 1
        }
    }
    want { print; found = 1 }
    END { if (!found) { print "release_notes.sh: no entry for version " target " in the changelog" > "/dev/stderr"; exit 1 } }
' "$changelog"
echo
echo "Full history: https://github.com/arcymonek/reportabuseipdb/blob/main/CHANGELOG.md"
