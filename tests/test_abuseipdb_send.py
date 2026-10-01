#!/usr/bin/env python3
"""Tests for abuseipdb_send.sh (stdlib unittest). Require Linux (GNU date, flock, jq).

Run (on the server or another Linux box), from the repository root:
    python3 -m unittest -v tests/test_abuseipdb_send.py
The generator and curl are MOCKS - the tests send nothing to AbuseIPDB or ntfy.
"""
import fcntl
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

SEND = Path(__file__).resolve().parent.parent / "abuseipdb_send.sh"
HAVE_TOOLS = all(shutil.which(t) for t in ("flock", "jq", "bash")) and \
    subprocess.run(["date", "-u", "-d", "@0"], capture_output=True).returncode == 0

KEY = "TESTKEY" + "a1B2c3D4" * 5           # 47 characters [A-Za-z0-9]
TOPIC = "secret-ntfy-topic-123"

FAKE_GEN = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["T"]
args = sys.argv[1:]
with open(os.path.join(T, "gen_args.jsonl"), "a") as f:
    f.write(json.dumps(args) + "\n")
if "--validate" in args:
    print("validate " + args[args.index("--validate") + 1])
    sys.exit(int(os.environ.get("FAKE_VALIDATE_RC", "0")))
rc = int(os.environ.get("FAKE_RC", "0"))
if os.environ.get("FAKE_STDERR"):
    print(os.environ["FAKE_STDERR"], file=sys.stderr)
if rc == 1:
    if not os.environ.get("FAKE_QUIET1"):          # a crash before main() exits 1 WITHOUT the message
        print("No qualifying reports - not writing a CSV.", file=sys.stderr)
    sys.exit(1)
if rc != 0:
    print("[ERROR] generator failure", file=sys.stderr); sys.exit(rc)
n = int(os.environ.get("FAKE_ROWS", "3"))
csv = "IP,Categories,ReportDate,Comment\r\n" + "".join(f"8.8.{i // 250}.{i % 250 + 1},\"15,21\",2026-09-28T01:00:00+00:00,Detected by CrowdSec\r\n" for i in range(n))
if "--dry-run" in args:
    sys.stdout.write(csv); print("[dry-run] %d rows" % n, file=sys.stderr)
else:
    out = args[args.index("--out") + 1]
    open(out, "w", newline="").write(csv)
    print("Wrote %d unique IPs to %s" % (n, out))
'''

MOCK_CURL = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["T"]
args = sys.argv[1:]
stdin = sys.stdin.read()
if "-K" in args:                                  # ntfy
    title = next((a[7:] for a in args if a.startswith("Title: ")), "")
    msg = args[args.index("-d") + 1] if "-d" in args else ""
    with open(os.path.join(T, "ntfy.jsonl"), "a") as f:
        f.write(json.dumps({"title": title, "msg": msg, "argv": args, "stdin": stdin}) + "\n")
    sys.exit(int(os.environ.get("MOCK_NTFY_RC", "0")))
import time
time.sleep(float(os.environ.get("MOCK_DELAY", "0")))
calls = os.path.join(T, "curl_calls")
n = int(open(calls).read()) + 1 if os.path.exists(calls) else 1
open(calls, "w").write(str(n))
with open(os.path.join(T, "curl_calls.jsonl"), "a") as f:
    f.write(json.dumps({"argv": args, "stdin": stdin}) + "\n")
seq = os.environ.get("MOCK_SEQ", "ok").split(",")
mode = seq[min(n, len(seq)) - 1]
csvpath = next(a[5:] for a in args if a.startswith("csv=@")).strip('"')   # curl strips the quotes
rows = len(open(csvpath, newline="").read().splitlines()) - 1
hdr_file = args[args.index("-D") + 1]
out_file = args[args.index("-o") + 1]
def reply(code, body="", headers=""):
    open(hdr_file, "w").write("HTTP/2 %s\r\n%s\r\n" % (code, headers))
    open(out_file, "w").write(body)
    sys.stdout.write(str(code)); sys.exit(0)
if mode == "ok":
    reply(200, json.dumps({"data": {"savedReports": rows, "invalidReports": []}}), "X-RateLimit-Remaining: 4\r\n")
if mode == "invalid":
    inv = [{"error": "Invalid IP", "input": "999.1.1.1", "rowNumber": 2}, {"error": "Invalid IP", "input": "x", "rowNumber": 3}]
    reply(200, json.dumps({"data": {"savedReports": rows - 2, "invalidReports": inv}}))
if mode == "short":
    reply(200, json.dumps({"data": {"savedReports": rows - 1, "invalidReports": []}}))
if mode == "429":
    reply(429, json.dumps({"errors": [{"detail": "Daily rate limit exceeded", "status": 429}]}), "Retry-After: 3600\r\n")
if mode in ("401", "403"):
    reply(int(mode), json.dumps({"errors": [{"detail": "Authentication failed", "status": int(mode)}]}))
if mode == "422":
    reply(422, json.dumps({"errors": [{"detail": "The csv file is malformed.", "status": 422}]}))
if mode == "500":
    reply(500, "<html>boom</html>")
if mode == "garbage":
    reply(200, "<html>not json</html>")
if mode == "nodata":
    reply(200, json.dumps({"data": {}}))
if mode == "timeout":
    open(hdr_file, "w").write(""); open(out_file, "w").write("")
    sys.stdout.write("000"); print("curl: (28) Operation timed out", file=sys.stderr); sys.exit(28)
raise SystemExit("unknown MOCK_SEQ: " + mode)
'''


@unittest.skipUnless(HAVE_TOOLS and SEND.exists(), "requires Linux with GNU date, flock and jq")
class SendBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.T = Path(self._td.name)
        self.sh = self.T / "abuseipdb_send.sh"
        shutil.copy(SEND, self.sh)
        self.sh.chmod(0o755)
        for name, body in (("fake_gen.py", FAKE_GEN), ("mockcurl", MOCK_CURL)):
            (self.T / name).write_text(body)
            (self.T / name).chmod(0o755)
        (self.T / "key").write_text(KEY + "\n")
        (self.T / "key").chmod(0o600)
        (self.T / "topic").write_text(TOPIC + "\n")
        # An empty HOME and an explicit config path: the tests never touch the real ~/.secrets.
        (self.T / "home").mkdir()
        self.conf = self.T / "abuseipdb.conf"
        self.conf.write_text("# test config\nOWN_NAME_MARKERS=example.org,host.example\n")
        self.env = dict(os.environ, T=str(self.T), PY_SCRIPT=str(self.T / "fake_gen.py"),
                        CURL_BIN=str(self.T / "mockcurl"), ABUSEIPDB_KEY_FILE=str(self.T / "key"),
                        NTFY_TOPIC_FILE=str(self.T / "topic"), RETRY_SLEEP="0", TMPDIR=str(self.T),
                        HOME=str(self.T / "home"), ABUSEIPDB_CONFIG=str(self.conf))
        self.env.pop("NTFY_URL", None)
        (self.T / ".state").mkdir()

    # --- helpers ---
    def run_sh(self, *args, **envover):
        env = dict(self.env, **envover)
        t0 = int(time.time())
        r = subprocess.run([str(self.sh), *args], capture_output=True, text=True, env=env, cwd=self.T)
        r.t0 = t0
        return r

    def set_wm(self, epoch):
        (self.T / ".state" / "abuseipdb_last_ok").write_text(f"{epoch}\n")

    def wm(self):
        p = self.T / ".state" / "abuseipdb_last_ok"
        return int(p.read_text().strip()) if p.exists() else None

    def jsonl(self, name):
        p = self.T / name
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def gen_calls(self):
        """Calls that GENERATE (without --validate)."""
        return [c for c in self.jsonl("gen_args.jsonl") if "--validate" not in c]

    def validate_calls(self):
        return [c for c in self.jsonl("gen_args.jsonl") if "--validate" in c]

    def curl_calls(self):
        return self.jsonl("curl_calls.jsonl")

    def ntfy(self):
        return self.jsonl("ntfy.jsonl")

    @staticmethod
    def iso(epoch):
        return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Happy(SendBase):
    def test_first_run_success(self):
        r = self.run_sh()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK: sent 3, saved 3, rejected 0", r.stdout)
        self.assertIn("remaining bulk-report limit: 4", r.stdout)
        self.assertEqual(len(self.curl_calls()), 1)
        self.assertEqual(self.ntfy(), [])
        self.assertGreaterEqual(self.wm(), r.t0)
        self.assertLessEqual(self.wm(), int(time.time()))
        g = self.gen_calls()[0]
        after, before = g[g.index("--after") + 1], g[g.index("--before") + 1]
        self.assertEqual(datetime.fromisoformat(before.replace("Z", "+00:00")).timestamp()
                         - datetime.fromisoformat(after.replace("Z", "+00:00")).timestamp(), 24 * 3600)
        self.assertIn("--out", g)
        self.assertTrue((self.T / "reports.csv").exists())

    def test_request_shape_and_key_never_in_argv(self):
        self.run_sh()
        c = self.curl_calls()[0]
        argv = " ".join(c["argv"])
        self.assertIn("Accept: application/json", argv)
        self.assertIn("https://api.abuseipdb.com/api/v2/bulk-report", argv)
        self.assertIn("csv=@", argv)
        self.assertNotIn(KEY, argv)                                     # the key is not on the process list
        self.assertEqual(c["stdin"], f"Key: {KEY}\n")                   # only through stdin
        self.assertIn("@-", c["argv"])
        self.assertNotIn(KEY, (self.T / "abuseipdb_send.sh").read_text())

    def test_key_and_topic_never_in_log_or_ntfy_argv(self):
        r = self.run_sh(FAKE_RC="2")                                    # forces an ntfy alert
        self.assertNotIn(KEY, r.stdout + r.stderr)
        n = self.ntfy()[0]
        self.assertNotIn(TOPIC, " ".join(n["argv"]))                    # the topic only through stdin (-K -)
        self.assertIn(TOPIC, n["stdin"])
        self.assertIn("-4", n["argv"])                                  # ntfy over IPv4 (IPv6 quota can be shared)
        self.assertNotIn(TOPIC, r.stdout + r.stderr)

    def test_window_from_watermark_is_exact(self):
        wm = int(time.time()) - 25 * 3600
        self.set_wm(wm)
        r = self.run_sh()
        self.assertEqual(r.returncode, 0, r.stdout)
        g = self.gen_calls()[0]
        self.assertEqual(g[g.index("--after") + 1], self.iso(wm))
        self.assertGreaterEqual(self.wm(), r.t0)
        since = int(g[g.index("--since") + 1].rstrip("s"))
        # window + 1 h: cscli --since filters by the alert's START, the window by its creation time
        self.assertAlmostEqual(since, 25 * 3600 + 3600, delta=3)

    def test_watermark_is_window_end_not_completion_time(self):
        """Watermark = the window end (--before), not the completion time: otherwise
        alerts that arrive while a run is in progress would fall into a gap and never be reported."""
        r = self.run_sh(MOCK_DELAY="2")
        self.assertEqual(r.returncode, 0, r.stdout)
        g = self.gen_calls()[0]
        before = int(datetime.fromisoformat(g[g.index("--before") + 1].replace("Z", "+00:00")).timestamp())
        self.assertEqual(self.wm(), before)
        self.assertGreaterEqual(int(time.time()) - self.wm(), 2)     # the run lasted >= 2 s

    def test_fetch_reaches_one_hour_before_the_window(self):
        self.run_sh()
        g = self.gen_calls()[0]
        since = int(g[g.index("--since") + 1].rstrip("s"))
        after = datetime.fromisoformat(g[g.index("--after") + 1].replace("Z", "+00:00")).timestamp()
        before = datetime.fromisoformat(g[g.index("--before") + 1].replace("Z", "+00:00")).timestamp()
        self.assertAlmostEqual(since, (before - after) + 3600, delta=3)

    def test_watermark_is_window_end_also_when_nothing_to_send(self):
        r = self.run_sh(FAKE_RC="1")
        g = self.gen_calls()[0]
        before = int(datetime.fromisoformat(g[g.index("--before") + 1].replace("Z", "+00:00")).timestamp())
        self.assertEqual(self.wm(), before)

    def test_consecutive_windows_share_boundary(self):
        """End of window N == start of window N+1 (no gaps, no overlap)."""
        self.run_sh()
        first_wm = self.wm()
        g1 = self.gen_calls()[0]
        self.assertEqual(g1[g1.index("--before") + 1], self.iso(first_wm))
        self.set_wm(first_wm - 24 * 3600 + 0)       # simulation: a day has passed
        # moving the watermark back a day means the "previous" run was 24 h ago
        r = self.run_sh()
        g2 = self.gen_calls()[1]
        self.assertEqual(g2[g2.index("--after") + 1], self.iso(first_wm - 24 * 3600))
        self.assertEqual(r.returncode, 0)


class Guard(SendBase):
    def test_second_run_within_20h_skipped(self):
        self.run_sh()
        r = self.run_sh()
        self.assertEqual(r.returncode, 0)
        self.assertIn("skipping: last report was", r.stdout)
        self.assertEqual(len(self.curl_calls()), 1)
        self.assertEqual(len(self.gen_calls()), 1)

    def test_force_overrides(self):
        self.run_sh()
        r = self.run_sh("--force")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("continuing thanks to --force", r.stdout)
        self.assertEqual(len(self.curl_calls()), 2)

    def test_lock_prevents_concurrent_run(self):
        with open(self.T / ".state" / "abuseipdb-send.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            r = self.run_sh()
        self.assertEqual(r.returncode, 0)
        self.assertIn("previous run is still in progress", r.stdout)
        self.assertEqual(self.gen_calls(), [])


class Window(SendBase):
    def test_lookback_capped_and_alerted(self):
        self.set_wm(int(time.time()) - 100 * 3600)
        r = self.run_sh()
        self.assertEqual(r.returncode, 0, r.stdout)
        g = self.gen_calls()[0]
        a = datetime.fromisoformat(g[g.index("--after") + 1].replace("Z", "+00:00")).timestamp()
        b = datetime.fromisoformat(g[g.index("--before") + 1].replace("Z", "+00:00")).timestamp()
        self.assertEqual(b - a, 48 * 3600)
        self.assertTrue(any("gap" in n["title"] for n in self.ntfy()))
        self.assertGreaterEqual(self.wm(), r.t0)

    def test_corrupt_watermark_uses_default_and_warns(self):
        (self.T / ".state" / "abuseipdb_last_ok").write_text("not a number\n")
        r = self.run_sh()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("corrupted watermark", r.stdout)
        self.assertTrue(any("corrupted" in n["title"] for n in self.ntfy()))
        self.assertGreaterEqual(self.wm(), r.t0)

    def test_future_watermark_fails(self):
        self.set_wm(int(time.time()) + 3600)
        r = self.run_sh()
        self.assertEqual(r.returncode, 1)
        self.assertIn("from the future", r.stdout)
        self.assertEqual(self.curl_calls(), [])


class Generator(SendBase):
    def test_no_rows_advances_watermark_and_removes_stale_csv(self):
        (self.T / "reports.csv").write_text("OLD FILE")
        r = self.run_sh(FAKE_RC="1")
        self.assertEqual(r.returncode, 0)
        self.assertIn("nothing to send", r.stdout)
        self.assertFalse((self.T / "reports.csv").exists())              # the stale file does not stay
        self.assertEqual(self.curl_calls(), [])
        self.assertGreaterEqual(self.wm(), r.t0)

    def test_exit_1_without_the_generators_message_is_a_failure(self):
        """Code 1 is also what a syntax error or a missing module gives: it must not close the window."""
        old = int(time.time()) - 30 * 3600
        self.set_wm(old)
        r = self.run_sh(FAKE_RC="1", FAKE_QUIET1="1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.wm(), old)                                 # the window is left to catch up on
        self.assertEqual(self.curl_calls(), [])
        self.assertEqual(len(self.ntfy()), 1)
        self.assertIn("without its 'No qualifying reports' message", r.stdout)

    def test_exit_1_with_the_message_still_closes_the_window(self):
        old = int(time.time()) - 30 * 3600
        self.set_wm(old)
        r = self.run_sh(FAKE_RC="1")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertGreater(self.wm(), old)
        self.assertEqual(self.ntfy(), [])

    def test_generator_error_alerts_and_keeps_watermark(self):
        old = int(time.time()) - 30 * 3600
        self.set_wm(old)
        (self.T / "reports.csv").write_text("OLD FILE")
        r = self.run_sh(FAKE_RC="2")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.wm(), old)                                 # the window is left to catch up on
        self.assertEqual(self.curl_calls(), [])
        self.assertFalse((self.T / "reports.csv").exists())              # the old file must not be sent
        self.assertEqual(len(self.ntfy()), 1)
        self.assertIn("code 2", r.stdout)

    def test_validation_failure_blocks_send(self):
        old = int(time.time()) - 30 * 3600
        self.set_wm(old)
        r = self.run_sh(FAKE_VALIDATE_RC="2")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.curl_calls(), [])
        self.assertEqual(self.wm(), old)
        self.assertIn("NOT sending", r.stdout)

    def test_missing_generator(self):
        r = self.run_sh(PY_SCRIPT=str(self.T / "missing.py"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.ntfy()), 1)


class Key(SendBase):
    def test_missing_key_file(self):
        r = self.run_sh(ABUSEIPDB_KEY_FILE=str(self.T / "missing"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.curl_calls(), [])

    def test_bad_key_format(self):
        for bad in ("short", "key with a space and a header\r\nX-Evil: 1", "a" * 30 + "\nX-Evil: 1"):
            (self.T / "key").write_text(bad)
            r = self.run_sh()
            self.assertEqual(r.returncode, 1, bad)
            self.assertEqual(self.curl_calls(), [], bad)
            self.assertIn("unexpected format", r.stdout)


class Config(SendBase):
    """The single config file (~/.secrets/abuseipdb.conf) and its fallbacks."""

    def use_config(self, text, **envover):
        """Key and topic only from the config: the explicit-file overrides are emptied."""
        self.conf.write_text(text)
        return dict(ABUSEIPDB_KEY_FILE="", NTFY_TOPIC_FILE="", **envover)

    def test_key_topic_and_url_come_from_the_config(self):
        env = self.use_config(f"OWN_NAME_MARKERS=example.org\nABUSEIPDB_API_KEY={KEY}\n"
                              f"NTFY_TOPIC={TOPIC}\nNTFY_URL=https://ntfy.example.test\n")
        r = self.run_sh(**env)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.curl_calls()[0]["stdin"], f"Key: {KEY}\n")
        r = self.run_sh("--force", FAKE_RC="2", **env)                  # forces an ntfy alert
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.ntfy()[0]["stdin"], f'url = "https://ntfy.example.test/{TOPIC}"\n')
        self.assertNotIn(KEY + TOPIC, r.stdout)

    def test_comments_spaces_and_crlf_are_handled(self):
        env = self.use_config(f"#ABUSEIPDB_API_KEY=wrongwrongwrongwrongwrong\r\n  OWN_NAME_MARKERS = example.org \r\n"
                              f"   ABUSEIPDB_API_KEY  =  {KEY}  \r\n")
        r = self.run_sh(**env)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.curl_calls()[0]["stdin"], f"Key: {KEY}\n")

    def test_config_is_parsed_not_executed(self):
        canary = self.T / "pwned"
        env = self.use_config(f"OWN_NAME_MARKERS=example.org\nNTFY_TOPIC=$(touch {canary})\n"
                              f"ABUSEIPDB_API_KEY={KEY}\nNTFY_URL=`touch {canary}`\n")
        self.run_sh("--force", FAKE_RC="2", **env)
        self.assertFalse(canary.exists())

    def test_generator_and_validator_get_the_config_path(self):
        self.run_sh()
        self.assertEqual(self.gen_calls()[0][:2], ["--config", str(self.conf)])
        self.assertEqual(self.validate_calls()[0][:2], ["--config", str(self.conf)])

    def test_legacy_files_are_a_deprecated_fallback(self):
        (self.T / "home" / ".secrets").mkdir()
        (self.T / "home" / ".secrets" / "abuseipdb_api_key").write_text(KEY + "\n")
        (self.T / "home" / ".secrets" / "ntfy_topic").write_text(TOPIC + "\n")
        env = self.use_config("OWN_NAME_MARKERS=example.org\n")
        r = self.run_sh(**env)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("deprecated file", r.stdout)
        self.assertEqual(self.curl_calls()[0]["stdin"], f"Key: {KEY}\n")
        self.run_sh("--force", FAKE_RC="2", **env)
        self.assertIn(TOPIC, self.ntfy()[0]["stdin"])

    def test_config_wins_over_legacy_files(self):
        (self.T / "home" / ".secrets").mkdir()
        (self.T / "home" / ".secrets" / "abuseipdb_api_key").write_text("LEGACY" + "x" * 30 + "\n")
        env = self.use_config(f"OWN_NAME_MARKERS=example.org\nABUSEIPDB_API_KEY={KEY}\n")
        r = self.run_sh(**env)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.curl_calls()[0]["stdin"], f"Key: {KEY}\n")
        self.assertNotIn("deprecated", r.stdout)

    def test_example_ntfy_topic_never_receives_alerts(self):
        env = self.use_config(f"OWN_NAME_MARKERS=real.test\nABUSEIPDB_API_KEY={KEY}\n"
                              "NTFY_TOPIC=your-private-ntfy-topic\n")
        r = self.run_sh(FAKE_RC="2", **env)                             # a failure that would alert
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.ntfy(), [])
        self.assertIn("NTFY_TOPIC is still the example value", r.stdout)

    def test_example_api_key_is_refused_with_a_clear_message(self):
        env = self.use_config("OWN_NAME_MARKERS=real.test\nABUSEIPDB_API_KEY=YOUR_ABUSEIPDB_API_KEY\n")
        r = self.run_sh(**env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ABUSEIPDB_API_KEY is still the example value", r.stdout)
        self.assertEqual(self.curl_calls(), [])

    def test_invalid_ntfy_topic_or_url_never_receives_alerts(self):
        for extra in (f"NTFY_TOPIC={TOPIC} # phone\n", 'NTFY_TOPIC=a"b\n',
                      f"NTFY_TOPIC={TOPIC}\nNTFY_URL=https://ntfy.example.test # mine\n"):
            env = self.use_config(f"OWN_NAME_MARKERS=real.test\nABUSEIPDB_API_KEY={KEY}\n{extra}")
            r = self.run_sh(FAKE_RC="2", **env)                         # a failure that would alert
            self.assertEqual(r.returncode, 1, extra)
            self.assertEqual(self.ntfy(), [], extra)
            self.assertIn("alert not sent", r.stdout, extra)

    def test_missing_key_everywhere_fails(self):
        env = self.use_config("OWN_NAME_MARKERS=example.org\n")
        r = self.run_sh(**env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("API key missing", r.stdout)
        self.assertEqual(self.curl_calls(), [])


class OwnNameMarkers(SendBase):
    """Fail closed: no markers = no upload (the own-name check would be inactive)."""

    def assert_refused(self, r):
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("OWN_NAME_MARKERS", r.stdout)
        self.assertEqual(self.gen_calls(), [])
        self.assertEqual(self.curl_calls(), [])
        self.assertIsNone(self.wm())
        self.assertEqual(len(self.ntfy()), 1)                           # the operator is alerted

    def test_config_without_markers_refuses_live_run(self):
        self.conf.write_text("ABUSEIPDB_API_KEY=" + KEY + "\n")
        self.assert_refused(self.run_sh())

    def test_empty_or_comma_only_markers_refuse_live_run(self):
        for value in ("", " , ,"):
            self.setUp()
            self.conf.write_text(f"OWN_NAME_MARKERS={value}\n")
            self.assert_refused(self.run_sh())

    def test_missing_config_file_refuses_live_run(self):
        self.conf.unlink()
        self.assert_refused(self.run_sh())

    def test_example_values_of_the_template_refuse_live_run(self):
        self.conf.write_text("OWN_NAME_MARKERS=your-domain.example,your-host.example\n")
        r = self.run_sh()
        self.assert_refused(r)
        self.assertIn("example values", r.stdout)

    def test_one_example_value_among_real_names_is_refused(self):
        self.conf.write_text("OWN_NAME_MARKERS=real.test,  YOUR-Host.Example \n")
        self.assert_refused(self.run_sh())

    def test_example_value_on_a_repeated_key_is_refused(self):
        # the example value comes FIRST: reading only the last line of the key would miss it
        self.conf.write_text("OWN_NAME_MARKERS=your-domain.example\nOWN_NAME_MARKERS=real.test\n")
        self.assert_refused(self.run_sh())

    def test_names_that_merely_contain_an_example_value_are_allowed(self):
        self.conf.write_text("OWN_NAME_MARKERS=my-your-domain.example.test\n")
        self.assertEqual(self.run_sh().returncode, 0)

    def test_example_values_dry_run_only_warns(self):
        self.conf.write_text("OWN_NAME_MARKERS=your-domain.example\n")
        r = self.run_sh("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("still holds the example values", r.stdout)
        self.assertIn("DRY-RUN: would send", r.stdout)

    def test_dry_run_only_warns(self):
        self.conf.write_text("# no markers\n")
        r = self.run_sh("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("a live run would be refused", r.stdout)
        self.assertIn("DRY-RUN: would send", r.stdout)


class Http(SendBase):
    def test_transient_500_then_ok(self):
        r = self.run_sh(MOCK_SEQ="500,500,ok")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(self.curl_calls()), 3)
        self.assertGreaterEqual(self.wm(), r.t0)
        self.assertEqual(self.ntfy(), [])

    def test_transient_exhausted(self):
        old = int(time.time()) - 30 * 3600
        self.set_wm(old)
        r = self.run_sh(MOCK_SEQ="500")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.curl_calls()), 3)
        self.assertEqual(self.wm(), old)
        self.assertEqual(len(self.ntfy()), 1)

    def test_curl_timeout_is_retried(self):
        r = self.run_sh(MOCK_SEQ="timeout,timeout,timeout")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.curl_calls()), 3)
        self.assertIn("curl=28", r.stdout)

    def test_429_not_retried_and_reports_retry_after(self):
        old = int(time.time()) - 30 * 3600
        self.set_wm(old)
        r = self.run_sh(MOCK_SEQ="429")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.curl_calls()), 1)
        self.assertIn("Retry-After 3600", r.stdout)
        self.assertEqual(self.wm(), old)
        self.assertEqual(len(self.ntfy()), 1)

    def test_401_and_403_not_retried(self):
        for code in ("401", "403"):
            self.setUp()
            r = self.run_sh(MOCK_SEQ=code)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(len(self.curl_calls()), 1)
            self.assertIn("API key", r.stdout)

    def test_422_shows_api_detail_and_not_retried(self):
        r = self.run_sh(MOCK_SEQ="422")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.curl_calls()), 1)
        self.assertIn("The csv file is malformed.", r.stdout)

    def test_200_with_non_json_or_missing_fields_fails(self):
        for mode in ("garbage", "nodata"):
            self.setUp()
            old = int(time.time()) - 30 * 3600
            self.set_wm(old)
            r = self.run_sh(MOCK_SEQ=mode)
            self.assertEqual(r.returncode, 1, mode)
            self.assertEqual(self.wm(), old, mode)

    def test_invalid_reports_alert_but_advance(self):
        r = self.run_sh(MOCK_SEQ="invalid", FAKE_ROWS="5")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("saved 3, rejected 2", r.stdout)
        self.assertIn("rejected: row 2: Invalid IP (999.1.1.1)", r.stdout)
        n = self.ntfy()
        self.assertEqual(len(n), 1)
        self.assertIn("Invalid IP x2", n[0]["msg"])
        self.assertGreaterEqual(self.wm(), r.t0)

    def test_count_mismatch_alerts(self):
        r = self.run_sh(MOCK_SEQ="short")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("mismatch" in n["title"] for n in self.ntfy()))

    def test_ntfy_failure_does_not_break_run(self):
        r = self.run_sh(MOCK_SEQ="invalid", FAKE_ROWS="5", MOCK_NTFY_RC="22")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ntfy ERROR", r.stdout)
        self.assertGreaterEqual(self.wm(), r.t0)


class DryRun(SendBase):
    def test_dry_run_has_no_side_effects(self):
        (self.T / "reports.csv").write_text("TODAYS FILE")
        r = self.run_sh("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("DRY-RUN: would send 3 reports", r.stdout)
        self.assertEqual(self.curl_calls(), [])
        self.assertEqual(self.ntfy(), [])
        self.assertIsNone(self.wm())
        self.assertEqual((self.T / "reports.csv").read_text(), "TODAYS FILE")   # untouched
        g = self.gen_calls()[0]
        self.assertIn("--dry-run", g)
        self.assertNotIn("--out", g)

    def test_dry_run_with_no_rows_does_not_advance_watermark(self):
        r = self.run_sh("--dry-run", FAKE_RC="1")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("nothing to send", r.stdout)
        self.assertIsNone(self.wm())

    def test_dry_run_alerts_are_printed_not_sent(self):
        r = self.run_sh("--dry-run", FAKE_RC="2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("[DRY-RUN ntfy", r.stdout)
        self.assertEqual(self.ntfy(), [])

    def test_dry_run_reports_guard_without_skipping(self):
        self.set_wm(int(time.time()) - 3600)
        r = self.run_sh("--dry-run")
        self.assertIn("would be SKIPPED", r.stdout)
        self.assertIn("DRY-RUN: would send", r.stdout)
        self.assertEqual(self.curl_calls(), [])


class Misc(SendBase):
    def test_args(self):
        self.assertEqual(self.run_sh("--bogus").returncode, 2)
        v = self.run_sh("--version")
        self.assertEqual((v.returncode, v.stdout.strip()), (0, "abuseipdb_send.sh v1.1.7"))
        self.assertEqual(self.run_sh("--help").returncode, 0)

    def test_log_trim_is_in_place_and_keeps_appending(self):
        log = self.T / "abuseipdb_cron.log"
        log.write_text("".join(f"old line {i}\n" for i in range(3000)))
        inode = log.stat().st_ino
        with open(log, "a") as fh:                                       # like `>> log` in cron
            r = subprocess.run([str(self.sh)], stdout=fh, stderr=subprocess.STDOUT, env=self.env, cwd=self.T)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(log.stat().st_ino, inode)                       # the same file (not mv)
        text = log.read_text()
        self.assertLess(len(text.splitlines()), 2100)
        self.assertIn("old line 2999", text)
        self.assertNotIn("old line 0\n", text)
        self.assertIn("OK: sent 3", text)                             # new entries arrived

    def test_temp_files_cleaned_up(self):
        self.run_sh()
        left = [p.name for p in self.T.iterdir()
                if p.name.startswith("abuseipdb_send.") and p.name != "abuseipdb_send.sh"]
        self.assertEqual(left, [])

    def test_shell_syntax(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(SEND)]).returncode, 0)


class AlertLimit(SendBase):
    def test_alert_limit_is_passed_to_the_generator(self):
        self.assertEqual(self.run_sh(ALERT_LIMIT="20000").returncode, 0)
        args = self.gen_calls()[0]
        self.assertEqual(args[args.index("--limit") + 1], "20000")

    def test_no_limit_argument_by_default(self):
        self.run_sh()
        self.assertNotIn("--limit", self.gen_calls()[0])

    def test_invalid_alert_limit_fails_before_generating(self):
        for bad in ("0", "abc", "-5", "10000000", "5 --dry-run"):
            r = self.run_sh("--force", ALERT_LIMIT=bad)
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("ALERT_LIMIT must be a whole number", r.stdout)
        self.assertEqual(self.gen_calls(), [])
        self.assertEqual(self.curl_calls(), [])


class Truncation(SendBase):
    """The generator marks 'data was cut off' lines with [TRUNCATED]; the wrapper alerts on them."""
    MARK = "[TRUNCATED] fetched 5000 alerts = the --limit (5000). Some alerts may have been cut off."

    def test_marker_sends_an_alert_but_the_run_completes(self):
        r = self.run_sh(FAKE_STDERR=self.MARK)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(self.curl_calls()), 1)                      # the upload still happens
        sent = self.ntfy()
        self.assertEqual([n["title"] for n in sent], ["abuseipdb: data cut off"])
        self.assertIn("--limit (5000)", sent[0]["msg"])
        self.assertGreaterEqual(self.wm(), r.t0)                         # the window is closed (that is why we alert)

    def test_marker_alert_also_when_there_is_nothing_to_send(self):
        r = self.run_sh(FAKE_RC="1", FAKE_STDERR=self.MARK)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.curl_calls(), [])
        self.assertEqual(len(self.ntfy()), 1)

    def test_marker_must_start_the_line(self):
        r = self.run_sh(FAKE_STDERR="note: [TRUNCATED] in the middle of a line")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.ntfy(), [])

    def test_dry_run_prints_the_alert_instead_of_sending(self):
        r = self.run_sh("--dry-run", FAKE_STDERR=self.MARK)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("[DRY-RUN ntfy p=3] abuseipdb: data cut off", r.stdout)
        self.assertEqual(self.ntfy(), [])


class SafeguardOff(SendBase):
    """The generator marks a safeguard that is not working with [SAFEGUARD-OFF]; the wrapper must alert."""
    MARK = "[SAFEGUARD-OFF] journalctl returned code 1 (Hint: no permission) - new SSH logins may be MISSING"

    def test_marker_sends_an_alert_but_the_run_completes(self):
        r = self.run_sh(FAKE_STDERR=self.MARK)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(self.curl_calls()), 1)                      # the other safeguards still hold: upload goes on
        sent = self.ntfy()
        self.assertEqual([n["title"] for n in sent], ["abuseipdb: safeguard not working"])
        self.assertIn("journalctl returned code 1", sent[0]["msg"])
        self.assertGreaterEqual(self.wm(), r.t0)

    def test_marker_alert_also_when_there_is_nothing_to_send(self):
        r = self.run_sh(FAKE_RC="1", FAKE_STDERR=self.MARK)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(self.ntfy()), 1)

    def test_marker_must_start_the_line(self):
        r = self.run_sh(FAKE_STDERR="note: [SAFEGUARD-OFF] in the middle of a line")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.ntfy(), [])

    def test_dry_run_prints_the_alert_instead_of_sending(self):
        r = self.run_sh("--dry-run", FAKE_STDERR=self.MARK)
        self.assertIn("[DRY-RUN ntfy p=4] abuseipdb: safeguard not working", r.stdout)
        self.assertEqual(self.ntfy(), [])


class AlertText(SendBase):
    def test_install_path_and_home_never_go_to_ntfy(self):
        """The alert passes through a public ntfy server; the full paths stay in the local log."""
        r = self.run_sh(PY_SCRIPT=str(self.T / "missing.py"))
        self.assertEqual(r.returncode, 1)
        msg = self.ntfy()[0]["msg"]
        self.assertNotIn(str(self.T), msg)
        self.assertIn("<dir>/missing.py", msg)
        self.assertIn(str(self.T), r.stdout)                             # the local log keeps the real path

    def test_home_directory_is_shortened(self):
        # a home outside the script directory (the usual layout is the other way round: script under home)
        with tempfile.TemporaryDirectory() as other_home:
            cfg = Path(other_home) / "abuseipdb.conf"
            cfg.write_text("OWN_NAME_MARKERS=example.org\n")             # no API key in it
            r = self.run_sh(HOME=other_home, ABUSEIPDB_CONFIG=str(cfg), ABUSEIPDB_KEY_FILE="")
            self.assertEqual(r.returncode, 1, r.stdout)
            msg = self.ntfy()[0]["msg"]
            self.assertNotIn(other_home, msg)
            self.assertIn("~/abuseipdb.conf", msg)


class UploadArgs(SendBase):
    def test_csv_path_is_quoted_for_curl(self):
        """curl -F splits an unquoted file name at ',' and ';', so the path must be quoted
        (curl removes the quotes itself; the mock does the same)."""
        self.run_sh()
        field = next(a for a in self.curl_calls()[0]["argv"] if a.startswith("csv=@"))
        self.assertEqual(field, f'csv=@"{self.T / "reports.csv"}"')


if __name__ == "__main__":
    unittest.main(verbosity=2)
