#!/bin/bash
# ====================================================
#     ABUSEIPDB SEND (cron: 05:30)
# ====================================================
# Generates the CSV (abuseipdb_report.py), validates it and sends it to AbuseIPDB
# (the bulk-report endpoint). Replaces the long `python3 ... && curl -s ...` line
# in the crontab, which did not check the API response.
#
#   abuseipdb_send.sh             normal run (cron)
#   abuseipdb_send.sh --dry-run   generates and checks, sends NOTHING, does not save
#                                 the watermark or the trusted-IP list
#   abuseipdb_send.sh --force     skips the "last report < 20 h ago" guard
#
# What it does beyond the old cron line:
#   * the time window is set by the WATERMARK of the last successful report
#     (.state/abuseipdb_last_ok): consecutive runs do not overlap (no double
#     reporting of the same events) and have no gaps; after an outage the next
#     run catches up, at most 48 h back.
#   * guard: a 2nd run within 20 h is skipped (AbuseIPDB guideline: report the
#     same IP ~once a day); --force overrides it.
#   * sends with the `Accept: application/json` header (without it API errors,
#     e.g. 429, arrive as an HTML page), checks the HTTP CODE and the JSON reply.
#   * the API key goes through stdin (`-H @-`), never through arguments (ps).
#   * retries only on transient errors (network, timeout, 5xx); 4xx (bad key,
#     422, 429) are NOT retried. Re-sending the same file is safe: AbuseIPDB
#     merges reports with an identical comment and categories within 24 h.
#   * ntfy alert on: generator/validation/upload error, 429, rejected reports
#     (invalidReports), a mismatched saved count, a gap > 48 h, data CUT OFF by a limit
#     (the generator marks such lines with [TRUNCATED]; the watermark still moves) and a safeguard
#     that is NOT working although the run continues (marked [SAFEGUARD-OFF], e.g. the journal cannot
#     be read, so SSH auto-trust is missing).
#   * generator exit code 1 means "nothing to report" only together with the generator's line
#     "No qualifying reports"; code 1 without it (a crash before main(), e.g. a syntax error) is a
#     failure: the watermark stays and the operator is alerted.
#   * the old reports.csv is deleted before generating - a stale file must never
#     be sent.
#
# Configuration: ONE file, ~/.secrets/abuseipdb.conf (chmod 600, outside the repo; see
# abuseipdb.conf.example for every key). It is parsed as plain text, never sourced.
# Read here: ABUSEIPDB_API_KEY, NTFY_TOPIC, NTFY_URL and OWN_NAME_MARKERS (a live run is
# REFUSED while the marker list is empty or still holds the example values; alerts are NOT
# sent to the example ntfy topic). The generator reads the same file (--config).
# Log: stdout (cron appends to abuseipdb_cron.log).

# One version for the whole project: keep it equal to SCRIPT_VERSION in abuseipdb_report.py (the pre-commit hook checks).
SCRIPT_VERSION="3.6.34"
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR/.state"
CSV="$SCRIPT_DIR/reports.csv"
LOG_FILE="$SCRIPT_DIR/abuseipdb_cron.log"
WM_FILE="$STATE_DIR/abuseipdb_last_ok"      # epoch of the end of the last successful window
API_URL="https://api.abuseipdb.com/api/v2/bulk-report"

CONFIG_FILE="${ABUSEIPDB_CONFIG:-$HOME/.secrets/abuseipdb.conf}"

# conf_get KEY: the last non-empty value of KEY in the config file (empty if the file
# or the key is missing). The file is read as text with sed; it is never executed.
conf_get() {
    [ -r "$CONFIG_FILE" ] || return 0
    sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$CONFIG_FILE" \
        | tr -d '\r' | sed 's/[[:space:]]*$//' | grep -v '^$' | tail -n 1
}

# conf_all KEY: every non-empty value of KEY (one per line), same text-only parsing as conf_get.
conf_all() {
    [ -r "$CONFIG_FILE" ] || return 0
    sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$CONFIG_FILE" \
        | tr -d '\r' | sed 's/[[:space:]]*$//' | grep -v '^$'
}

# The example values of abuseipdb.conf.example. Copied unchanged they would make the safeguards
# look active while doing nothing (own names nobody uses) or publish the alerts on a topic
# anyone can guess, so they are refused (see below and notify).
PLACEHOLDER_TOPIC="your-private-ntfy-topic"
PLACEHOLDER_KEY="YOUR_ABUSEIPDB_API_KEY"
# ntfy topic names are letters, digits, '_' and '-' (at most 64). Anything else is a typo or a
# pasted comment, and a '"' would even break the curl config the URL is passed through.
TOPIC_RE='^[A-Za-z0-9_-]{1,64}$'
URL_RE='^https?://[^[:space:]"\\]+$'
PLACEHOLDER_MARKERS_RE='your-domain\.example|your-host\.example'

# --- Settings (environment variables are for tests; cron does not set them, except ALERT_LIMIT) ---
PY_SCRIPT="${PY_SCRIPT:-$SCRIPT_DIR/abuseipdb_report.py}"
KEY_FILE="${ABUSEIPDB_KEY_FILE:-}"           # explicit key file overrides the config
CURL_BIN="${CURL_BIN:-curl}"
NTFY_URL="${NTFY_URL:-$(conf_get NTFY_URL)}"
NTFY_URL="${NTFY_URL:-https://ntfy.sh}"
NTFY_TOPIC_FILE="${NTFY_TOPIC_FILE:-}"       # explicit topic file overrides the config
DEFAULT_WINDOW_H="${DEFAULT_WINDOW_H:-24}"   # window on the first run (no watermark)
MAX_LOOKBACK_H="${MAX_LOOKBACK_H:-48}"       # furthest back after an outage
MIN_INTERVAL_H="${MIN_INTERVAL_H:-20}"       # guard against more frequent reporting
ALERT_LIMIT="${ALERT_LIMIT:-}"               # passed as --limit when set (default: the generator's 5000)
# cscli --since filters on the START of an alert, while the generator cuts the window by the alert's
# creation time. A slow bucket can start long before it is created (measured: up to ~2 minutes), so the
# fetch reaches back this much further than the window; the generator's --after/--before keep the
# window exact, the margin only stops such alerts from being lost at the boundary.
SINCE_MARGIN_S="${SINCE_MARGIN_S:-3600}"
RETRIES="${RETRIES:-3}"
RETRY_SLEEP="${RETRY_SLEEP:-60}"             # seconds * attempt number

usage() {
    echo "Usage: abuseipdb_send.sh [--dry-run] [--force]"
    echo "       abuseipdb_send.sh [--version|-v] [--help|-h]"
}

DRY=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --force) FORCE=1 ;;
        --version|-v) echo "abuseipdb_send.sh v${SCRIPT_VERSION}"; exit 0 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown argument: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

log() { printf '%s [send] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

trim_log() {
    # Trim IN PLACE (cat >), because cron holds the file descriptor open (>>):
    # replacing the file with mv would lose further entries.
    [ -f "$LOG_FILE" ] || return 0
    if [ "$(wc -l < "$LOG_FILE")" -gt 2500 ]; then
        tail -n 2000 "$LOG_FILE" > "$LOG_FILE.tmp" && cat "$LOG_FILE.tmp" > "$LOG_FILE"
        rm -f "$LOG_FILE.tmp"
    fi
}

# resolve_topic: prints the ntfy topic. Order: explicit file (env), config key.
resolve_topic() {
    local t
    if [ -n "$NTFY_TOPIC_FILE" ]; then
        [ -r "$NTFY_TOPIC_FILE" ] && tr -d '[:space:]' < "$NTFY_TOPIC_FILE"
        return 0
    fi
    t="$(conf_get NTFY_TOPIC | tr -d '[:space:]')"
    printf '%s' "$t"
}

# --- ntfy: notify TITLE PRIORITY(1-5) TAGS BODY. Titles are ASCII (HTTP header). ---
notify() {
    local title=$1 prio=$2 tags=$3 msg=$4 topic err
    # The alert travels through the public ntfy server: do not send the install path or the user name.
    # The full text stays in the local log.
    msg="${msg//"$SCRIPT_DIR"/<dir>}"
    msg="${msg//"$HOME"/\~}"
    if [ "$DRY" -eq 1 ]; then
        printf '[DRY-RUN ntfy p=%s] %s | %s\n' "$prio" "$title" "$msg"
        return 0
    fi
    topic="$(resolve_topic)"
    [ -n "$topic" ] || { log "ERROR: no ntfy topic (set NTFY_TOPIC in $CONFIG_FILE) - alert not sent: $title"; return 1; }
    [ "$topic" != "$PLACEHOLDER_TOPIC" ] || { log "ERROR: NTFY_TOPIC is still the example value (set your own private topic in $CONFIG_FILE) - alert not sent: $title"; return 1; }
    [[ "$topic" =~ $TOPIC_RE ]] || { log "ERROR: NTFY_TOPIC has invalid characters (letters, digits, '_' and '-' only, at most 64; no comment after the value) - alert not sent: $title"; return 1; }
    [[ "$NTFY_URL" =~ $URL_RE ]] || { log "ERROR: NTFY_URL is not a plain http(s) URL (no spaces, quotes or a comment after the value) - alert not sent: $title"; return 1; }
    # The URL with the topic goes through stdin (-K -), so it does not show up in the process list.
    # -4: ntfy.sh counts its daily message quota per address, and a shared IPv6 range can be
    # exhausted by other senders (HTTP 429 code 42908) while IPv4 still works. Remove -4 only
    # on an IPv6-only host.
    if err=$(printf 'url = "%s/%s"\n' "$NTFY_URL" "$topic" | "$CURL_BIN" -4 -fsS --max-time 10 -K - \
            -H "Title: $title" -H "Priority: $prio" -H "Tags: $tags" -d "$msg" -o /dev/null 2>&1); then
        log "ntfy sent: $title"
        return 0
    fi
    log "ntfy ERROR (${err//$topic/***}): $title"
    return 1
}

TMPFILES=()
cleanup() { [ "${#TMPFILES[@]}" -eq 0 ] || rm -f "${TMPFILES[@]}"; }
trap cleanup EXIT
# new_tmp VARIABLE: creates a temporary file and stores its path in VARIABLE.
# Must NOT be called through $(...) - the subshell would lose the cleanup list.
new_tmp() { local f; f="$(mktemp "${TMPDIR:-/tmp}/abuseipdb_send.XXXXXX")" || exit 1; TMPFILES+=("$f"); printf -v "$1" '%s' "$f"; }

# fail MESSAGE: log + ntfy (prio 4) + exit 1. The watermark is NOT advanced,
# so the next run catches up on this window.
fail() {
    log "ERROR: $*"
    notify "abuseipdb: reporting ERROR" 4 warning "$* (watermark unchanged, the next run will catch up on the window)"
    exit 1
}

to_iso() { date -u -d "@$1" '+%Y-%m-%dT%H:%M:%SZ'; }
human_age() { awk -v s="$1" 'BEGIN { printf "%.1f h", s/3600 }'; }

set_watermark() {
    [ "$DRY" -eq 1 ] && return 0
    printf '%s\n' "$1" > "$WM_FILE.tmp" && mv "$WM_FILE.tmp" "$WM_FILE"
}

mkdir -p "$STATE_DIR"
exec 9> "$STATE_DIR/abuseipdb-send.lock"
flock -n 9 || { log "previous run is still in progress - skipping"; exit 0; }
trim_log

log "start v${SCRIPT_VERSION}$([ "$DRY" -eq 1 ] && echo ' (DRY-RUN)')$([ "$FORCE" -eq 1 ] && echo ' (--force)')"
[ -f "$PY_SCRIPT" ] || fail "generator missing: $PY_SCRIPT"
command -v jq > /dev/null || fail "jq is not installed (apt install jq)"

# Fail closed: without own-name markers the check that a comment does not reveal our
# domains/host would be silently inactive, so a live run is refused (dry-run only warns).
if [ -z "$(conf_get OWN_NAME_MARKERS | tr -d '[:space:],')" ]; then
    if [ "$DRY" -eq 1 ]; then
        log "WARNING: OWN_NAME_MARKERS is empty or the config is unreadable ($CONFIG_FILE) - a live run would be refused"
    else
        fail "OWN_NAME_MARKERS is empty or the config is unreadable ($CONFIG_FILE): the own-name check of report comments would be inactive - NOT sending"
    fi
fi

# The example marker values protect nothing: refuse a live run, warn on a dry run.
if conf_all OWN_NAME_MARKERS | tr ',' '\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
        | tr '[:upper:]' '[:lower:]' | grep -qxE "$PLACEHOLDER_MARKERS_RE"; then
    if [ "$DRY" -eq 1 ]; then
        log "WARNING: OWN_NAME_MARKERS still holds the example values ($CONFIG_FILE) - a live run would be refused"
    else
        fail "OWN_NAME_MARKERS still holds the example values of abuseipdb.conf.example ($CONFIG_FILE): set your own domains and host names - NOT sending"
    fi
fi

# --- Time window: (AFTER, NOW] ---
NOW="$(date +%s)"
HAVE_WM=0
AFTER=$((NOW - DEFAULT_WINDOW_H * 3600))
if [ -f "$WM_FILE" ]; then
    wm="$(tr -d '[:space:]' < "$WM_FILE")"
    if [[ "$wm" =~ ^[0-9]{9,11}$ ]]; then
        AFTER=$wm
        HAVE_WM=1
    else
        log "WARNING: corrupted watermark $WM_FILE ('${wm:0:20}') - using the default window of ${DEFAULT_WINDOW_H} h"
        notify "abuseipdb: corrupted watermark" 3 warning "File $WM_FILE has invalid content; using the default window of ${DEFAULT_WINDOW_H} h."
    fi
else
    log "no watermark of the last report - default window of ${DEFAULT_WINDOW_H} h"
fi

AGE=$((NOW - AFTER))
[ "$AGE" -ge 0 ] || fail "watermark from the future (clock skew?): after=$AFTER now=$NOW"

if [ "$HAVE_WM" -eq 1 ] && [ "$AGE" -lt $((MIN_INTERVAL_H * 3600)) ]; then
    if [ "$FORCE" -eq 1 ]; then
        log "WARNING: last report was $(human_age "$AGE") ago (< ${MIN_INTERVAL_H} h) - continuing thanks to --force"
    elif [ "$DRY" -eq 1 ]; then
        log "(dry-run) a normal run would be SKIPPED: last report was $(human_age "$AGE") ago (< ${MIN_INTERVAL_H} h)"
    else
        log "skipping: last report was $(human_age "$AGE") ago (< ${MIN_INTERVAL_H} h; AbuseIPDB guideline: ~1x a day). --force overrides."
        exit 0
    fi
fi

if [ "$AGE" -gt $((MAX_LOOKBACK_H * 3600)) ]; then
    log "WARNING: gap of $(human_age "$AGE") > ${MAX_LOOKBACK_H} h - window cut to ${MAX_LOOKBACK_H} h (older alerts skipped)"
    notify "abuseipdb: gap in reports" 3 warning "Last successful report was $(human_age "$AGE") ago; window cut to ${MAX_LOOKBACK_H} h."
    AFTER=$((NOW - MAX_LOOKBACK_H * 3600))
    AGE=$((NOW - AFTER))
fi
AFTER_ISO="$(to_iso "$AFTER")"
NOW_ISO="$(to_iso "$NOW")"
log "window: ($AFTER_ISO, $NOW_ISO] = $(human_age "$AGE")"

# --- Generating the CSV ---
[ "$DRY" -eq 1 ] || rm -f "$CSV"    # a stale file must not be sent (dry-run touches nothing)
new_tmp GEN_OUT
PYARGS=(--config "$CONFIG_FILE" --since "$((AGE + SINCE_MARGIN_S))s" --after "$AFTER_ISO" --before "$NOW_ISO")
# ALERT_LIMIT raises the number of alerts read from cscli after a "data cut off" alert; set it in
# the crontab line, e.g.  30 5 * * * ALERT_LIMIT=20000 /path/abuseipdb_send.sh >> ...
if [ -n "$ALERT_LIMIT" ]; then
    [[ "$ALERT_LIMIT" =~ ^[1-9][0-9]{0,6}$ ]] || fail "ALERT_LIMIT must be a whole number from 1 to 9999999 (got '${ALERT_LIMIT:0:20}')"
    PYARGS+=(--limit "$ALERT_LIMIT")
fi
if [ "$DRY" -eq 1 ]; then
    new_tmp DRY_CSV
    python3 "$PY_SCRIPT" "${PYARGS[@]}" --dry-run > "$DRY_CSV" 2> "$GEN_OUT"
    GEN_RC=$?
else
    python3 "$PY_SCRIPT" "${PYARGS[@]}" --out "$CSV" > "$GEN_OUT" 2>&1
    GEN_RC=$?
fi
while IFS= read -r line; do [ -n "$line" ] && log "  generator: $line"; done < "$GEN_OUT"

# The generator starts every message about CUT-OFF data (the alert --limit, the row or size
# limit of the CSV) with [TRUNCATED]. The watermark moves on anyway, so without this alert
# nobody would notice that some alerts were never reported.
TRUNCATED="$(grep '^\[TRUNCATED]' "$GEN_OUT" | cut -c1-300 | head -n 3 | tr '\n' ' ')"
if [ -n "$TRUNCATED" ]; then
    notify "abuseipdb: data cut off" 3 warning "$TRUNCATED(the window is closed; the cut-off alerts will not be reported)"
fi

# A safeguard that is not working (but does not stop the run) is marked [SAFEGUARD-OFF] by the generator.
# Quiet in the log only would let the operator report their own address without ever knowing.
SAFEGUARD_OFF="$(grep '^\[SAFEGUARD-OFF]' "$GEN_OUT" | cut -c1-300 | head -n 3 | tr '\n' ' ')"
if [ -n "$SAFEGUARD_OFF" ]; then
    notify "abuseipdb: safeguard not working" 4 warning "$SAFEGUARD_OFF(the run continues with the other safeguards; fix this before the next run)"
fi

case "$GEN_RC" in
    0) ;;
    1)
        # Code 1 is "nothing to report" ONLY with the generator's own message; an interpreter failure before
        # main() (syntax error, missing module) also exits with 1 and must not close the window silently.
        grep -q '^No qualifying reports' "$GEN_OUT" \
            || fail "generator exited with code 1 without its 'No qualifying reports' message (crashed before it could report?)"
        log "no qualifying reports in the window - nothing to send"
        set_watermark "$NOW"
        exit 0
        ;;
    *) fail "generator exited with code $GEN_RC" ;;
esac

if [ "$DRY" -eq 1 ]; then
    ROWS=$(( $(wc -l < "$DRY_CSV") - 1 ))
    log "DRY-RUN: would send $ROWS reports; nothing sent, watermark and trusted-IP list unchanged"
    tail -n +2 "$DRY_CSV" | head -n 3 | cut -c1-170 | while IFS= read -r line; do log "  example: $line"; done
    exit 0
fi

# Independent validation of the file right before sending (in addition to the generator's own)
new_tmp VAL_OUT
python3 "$PY_SCRIPT" --config "$CONFIG_FILE" --validate "$CSV" > "$VAL_OUT" 2>&1 || {
    while IFS= read -r line; do log "  validation: $line"; done < "$VAL_OUT"
    fail "file $CSV failed validation against the AbuseIPDB requirements - NOT sending"
}
ROWS=$(( $(wc -l < "$CSV") - 1 ))
log "file ready: $ROWS reports, validation OK"

# --- API key (in memory only; never in arguments or the log) ---
if [ -n "$KEY_FILE" ]; then                       # explicit key file (tests)
    KEY_SRC="$KEY_FILE"
    [ -r "$KEY_FILE" ] || fail "API key file missing/unreadable ($KEY_FILE)"
    KEY="$(tr -d '[:space:]' < "$KEY_FILE")"
else
    KEY_SRC="$CONFIG_FILE"
    KEY="$(conf_get ABUSEIPDB_API_KEY | tr -d '[:space:]')"
    [ -n "$KEY" ] || fail "API key missing: set ABUSEIPDB_API_KEY in $CONFIG_FILE"
fi
[ "$KEY" != "$PLACEHOLDER_KEY" ] || fail "ABUSEIPDB_API_KEY is still the example value of abuseipdb.conf.example: set your own key in $KEY_SRC"
[[ "$KEY" =~ ^[A-Za-z0-9]{20,}$ ]] || fail "API key has an unexpected format (source $KEY_SRC)"

# --- Upload: retries only for transient errors ---
new_tmp HDRS; new_tmp BODY; new_tmp CERR
attempt=1
while :; do
    code="$(printf 'Key: %s\n' "$KEY" | "$CURL_BIN" -sS --connect-timeout 15 --max-time 120 \
        -H @- -H 'Accept: application/json' -F "csv=@\"$CSV\"" \
        -D "$HDRS" -o "$BODY" -w '%{http_code}' "$API_URL" 2> "$CERR")"
    crc=$?
    if [ "$crc" -ne 0 ] || [[ "$code" =~ ^(5[0-9][0-9]|408)$ ]]; then
        log "attempt $attempt/$RETRIES: transient error (curl=$crc, HTTP=${code:-none}) $(tr '\n' ' ' < "$CERR" | cut -c1-160)"
        if [ "$attempt" -lt "$RETRIES" ]; then
            sleep $((RETRY_SLEEP * attempt))
            attempt=$((attempt + 1))
            continue
        fi
        fail "upload to AbuseIPDB failed after $RETRIES attempts (curl=$crc, HTTP=${code:-none})"
    fi
    break
done
unset KEY

REMAINING="$(grep -i '^x-ratelimit-remaining:' "$HDRS" | tr -dc '0-9' | head -c 8)"
case "$code" in
    200) ;;
    429)
        retry="$(grep -i '^retry-after:' "$HDRS" | tr -dc '0-9' | head -c 8)"
        fail "AbuseIPDB daily limit exceeded (HTTP 429, Retry-After ${retry:-?} s)"
        ;;
    401|403) fail "AbuseIPDB rejected the API key (HTTP $code) - check $KEY_SRC" ;;
    *)
        detail="$(jq -r '[.errors[]?.detail] | join("; ")' "$BODY" 2> /dev/null | tr '\n' ' ' | cut -c1-200)"
        fail "AbuseIPDB returned HTTP $code: ${detail:-no details (the reply is not JSON)}"
        ;;
esac

SAVED="$(jq -er '.data.savedReports | numbers' "$BODY" 2> /dev/null)" \
    || fail "HTTP 200 reply without the data.savedReports field (unexpected format)"
INVALID="$(jq -er '.data.invalidReports | length' "$BODY" 2> /dev/null)" \
    || fail "HTTP 200 reply without the data.invalidReports field (unexpected format)"

log "OK: sent $ROWS, saved $SAVED, rejected $INVALID; window ($AFTER_ISO, $NOW_ISO]; remaining bulk-report limit: ${REMAINING:-?}"

if [ "$INVALID" -gt 0 ]; then
    jq -r '.data.invalidReports[:20][] | "  rejected: row \(.rowNumber): \(.error) (\(.input))"' "$BODY" 2> /dev/null \
        | while IFS= read -r line; do log "$line"; done
    summary="$(jq -r '[.data.invalidReports[].error] | group_by(.) | map("\(.[0]) x\(length)") | join(", ")' "$BODY" 2> /dev/null)"
    notify "abuseipdb: rejected reports" 3 warning "$INVALID of $ROWS rejected: ${summary:-?}. Details in abuseipdb_cron.log."
fi
if [ $((SAVED + INVALID)) -ne "$ROWS" ]; then
    log "WARNING: saved $SAVED + rejected $INVALID != sent $ROWS"
    notify "abuseipdb: count mismatch" 3 warning "Sent $ROWS, saved $SAVED, rejected $INVALID."
fi

# Accepted reports are stored on the AbuseIPDB side; rejected ones (bad IP/category)
# would not change on a re-send, so we advance the watermark in both cases.
set_watermark "$NOW"
log "watermark updated: $NOW_ISO"
exit 0
