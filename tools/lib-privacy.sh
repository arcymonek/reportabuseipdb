# Shared by tools/pre-commit and tools/commit-msg (sourced, not run). It is not a git hook itself.
# The privacy rules in one place, so the hook for files and the hook for messages cannot drift apart:
#   privacy_markers FILE   write the OWN_NAME_MARKERS of the local config (one per line) to FILE
#   privacy_strip          stdin -> stdout, with the few strings that are allowed in the repository removed
#
# The allowed strings are assembled from pieces so that this file does not contain them itself
# (it would trip its own scan).
site="arkadiusz""polak.pl"
privacy_conf="${ABUSEIPDB_CONFIG:-$HOME/.secrets/abuseipdb.conf}"

privacy_markers() {
    : > "$1"
    [ -r "$privacy_conf" ] || return 0
    sed -n 's/^[[:space:]]*OWN_NAME_MARKERS[[:space:]]*=//p' "$privacy_conf" | tr ',' '\n' | tr -d '\r' \
        | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep -v '^$' > "$1"
}

# esc() makes a string safe inside a sed pattern.
privacy_esc() { printf '%s' "$1" | sed 's/[][\.*^$/]/\\&/g'; }

# Only the author's contact details are allowed in the repository (see AGENTS.md / CLAUDE.md):
#   github@<domain>, the bare domain, the author's name, and the GitHub profile path.
# The bare domain is removed ONLY when it is not the tail of a longer host name: "nas.<domain>" is a
# host of the operator's own server and must still be caught by the markers, and "someone@<domain>" is
# not the one allowed address. So the domain counts only after a character that cannot be part of a
# host name or an e-mail local part.
privacy_strip() {
    sed -E \
        -e "s/github@$(privacy_esc "$site")//g" \
        -e "s/(^|[^A-Za-z0-9._@-])$(privacy_esc "$site")/\\1/g" \
        -e "s/Arkadiusz"" Polak//g" \
        -e "s/github\\.com\\/arcy""monek\\///g"
}
