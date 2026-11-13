import copy
import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import autostop_manager as am  # noqa: E402

UTC = dt.timezone.utc
# Tuesday 10 Nov 2026 15:00 UTC (template saved mid-week)
NOW = dt.datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
QH_LONDON = {"time": "13:32", "timezone": "Europe/London"}


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def cfg(**over):
    c = am.deep_merge(am.DEFAULT_CONFIG, over)
    c.update(template="t1", coder_url="https://coder.example", coder_token="x")
    return c


def template(days=("sunday",), updated=NOW - dt.timedelta(days=30)):
    return {
        "id": "tpl-1", "name": "t1", "created_by_id": "admin-id", "organization_name": "coder",
        "updated_at": iso(updated),
        "autostop_requirement": {"days_of_week": list(days), "weeks": 2},
    }


def workspace(wid="ws-1", deadline=None, max_deadline=None, last_used=NOW, status="running", prebuild=False,
              started=NOW - dt.timedelta(hours=1)):
    return {
        "id": wid, "name": wid, "owner_id": "user-" + wid, "owner_name": "owner-" + wid,
        "template_id": "tpl-1", "is_prebuild": prebuild, "last_used_at": iso(last_used),
        "latest_build": {
            "status": status,
            "job": {"completed_at": iso(started)},
            "deadline": iso(deadline) if deadline else am.ZERO_TIME,
            "max_deadline": iso(max_deadline) if max_deadline else am.ZERO_TIME,
        },
    }


class FakeClient:
    def __init__(self, tpl, workspaces, fail_stop=False, qh=None):
        self.tpl, self.ws, self.fail_stop = tpl, workspaces, fail_stop
        self.qh = qh or {}  # owner_id -> quiet-hours response (default QH_LONDON)
        self.stopped = []

    def find_template(self, name, org=""):
        if name != self.tpl["name"]:
            raise am.ConfigError("nope")
        return self.tpl

    def template_workspaces(self, tpl):
        return self.ws

    def user(self, uid):
        return {"email": uid + "@example.com"}

    def quiet_hours(self, uid):
        return self.qh.get(uid, QH_LONDON)

    def stop_workspace(self, wid):
        if self.fail_stop:
            resp = type("R", (), {"status_code": 500})()
            raise am.requests.HTTPError(response=resp)
        self.stopped.append(wid)


# ------------------------------------------------------------------ parsing

def test_parse_time_zero_and_garbage():
    assert am.parse_time(am.ZERO_TIME) is None
    assert am.parse_time("") is None
    assert am.parse_time("nope") is None
    assert am.parse_time("2026-11-15T13:32:00Z") == dt.datetime(2026, 11, 15, 13, 32, tzinfo=UTC)


def test_effective_stop_is_earliest_nonzero():
    d, m = NOW + dt.timedelta(hours=3), NOW + dt.timedelta(days=5)
    assert am.effective_stop({"deadline": iso(d), "max_deadline": iso(m)}) == d
    assert am.effective_stop({"deadline": am.ZERO_TIME, "max_deadline": iso(m)}) == m
    assert am.effective_stop({"deadline": am.ZERO_TIME, "max_deadline": am.ZERO_TIME}) is None


# ------------------------------------------------------------------ off-schedule (now+2h clamp)

def test_clamped_max_deadline_is_off_schedule():
    clamped = NOW + dt.timedelta(hours=2)  # Tuesday 17:00 -> the now+2h clamp
    rec = am.classify(workspace(deadline=clamped, max_deadline=clamped), template(), QH_LONDON, cfg(), NOW)
    assert "imminent_stop" in rec["flags"]
    assert "off_schedule" in rec["flags"]
    assert "tuesday" in rec["reasons"][0]


def test_legit_sunday_quiet_hours_stop_not_off_schedule():
    now = dt.datetime(2026, 11, 15, 11, 0, tzinfo=UTC)  # Sunday morning
    legit = dt.datetime(2026, 11, 15, 13, 32, tzinfo=UTC)  # 13:32 Europe/London (GMT)
    rec = am.classify(workspace(max_deadline=legit, last_used=now), template(), QH_LONDON, cfg(), now)
    assert rec["flags"] == ["imminent_stop"]


def test_right_day_wrong_time_is_off_schedule():
    now = dt.datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
    wrong = dt.datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
    rec = am.classify(workspace(max_deadline=wrong, last_used=now), template(), QH_LONDON, cfg(), now)
    assert "off_schedule" in rec["flags"]


def test_clamp_close_to_quiet_hours_detected_by_seconds():
    # Clamp landed 1 minute after quiet-hours start on a required day: time check
    # alone (5 min tolerance) would miss it; the non-minute-aligned value does not.
    now = dt.datetime(2026, 11, 15, 11, 31, 7, 123456, tzinfo=UTC)
    clamped = now + dt.timedelta(hours=2)  # 13:31:07.123456 vs quiet hours 13:32
    rec = am.classify(workspace(max_deadline=clamped, last_used=now), template(), QH_LONDON, cfg(), now)
    assert "off_schedule" in rec["flags"]
    assert "clamp" in rec["reasons"][0]


def test_quiet_hours_respect_dst_timezone():
    # Sydney is UTC+11 in November: quiet hours 00:00 local Monday == Sunday 13:00 UTC
    qh = {"time": "00:00", "timezone": "Australia/Sydney"}
    stop = dt.datetime(2026, 11, 15, 13, 0, tzinfo=UTC)
    off, why = am.is_off_schedule(stop, template(days=("monday",)), qh)
    assert not off, why


def test_no_days_of_week_never_off_schedule():
    clamped = NOW + dt.timedelta(hours=2)
    rec = am.classify(workspace(max_deadline=clamped), template(days=()), QH_LONDON, cfg(), NOW)
    assert "off_schedule" not in rec["flags"]


def test_deadline_before_max_deadline_not_off_schedule():
    # TTL deadline drives the stop, not the requirement
    d = NOW + dt.timedelta(hours=1)
    m = NOW + dt.timedelta(hours=2)
    rec = am.classify(workspace(deadline=d, max_deadline=m), template(), QH_LONDON, cfg(), NOW)
    assert rec["flags"] == ["imminent_stop"]


def test_idle_flag():
    rec = am.classify(workspace(last_used=NOW - dt.timedelta(hours=30)), template(), QH_LONDON, cfg(), NOW)
    assert rec["flags"] == ["idle"]


# ------------------------------------------------------------------ dedupe

def test_dedupe_notifies_once_when_entering_window():
    c = cfg()  # 4h window, 30m interval
    tpl = template()
    for hours, expected in ((3.75, True), (3.25, False), (1.0, False)):
        stop = NOW + dt.timedelta(hours=hours)
        rec = am.classify(workspace(deadline=stop), tpl, QH_LONDON, c, NOW)
        assert am.should_notify(rec, tpl, c, NOW) is expected, hours


def test_dedupe_notifies_after_recent_template_save():
    c = cfg()
    tpl = template(updated=NOW - dt.timedelta(minutes=10))
    clamped = NOW + dt.timedelta(hours=2)
    rec = am.classify(workspace(max_deadline=clamped), tpl, QH_LONDON, c, NOW)
    assert am.should_notify(rec, tpl, c, NOW)


def test_dedupe_disabled():
    c = cfg(notify={"dedupe": False})
    rec = am.classify(workspace(deadline=NOW + dt.timedelta(hours=1)), template(), QH_LONDON, c, NOW)
    assert am.should_notify(rec, template(), c, NOW)


# ------------------------------------------------------------------ run()

def test_run_report_only_no_emails_no_stops(capsys):
    fc = FakeClient(template(), [workspace(last_used=NOW - dt.timedelta(days=3))])
    assert am.run(cfg(), fc, NOW) == 0
    out = capsys.readouterr().out
    assert "EMAIL" not in out and fc.stopped == []


def test_run_stop_dry_run_does_not_stop(capsys):
    fc = FakeClient(template(), [workspace(last_used=NOW - dt.timedelta(days=3))])
    assert am.run(cfg(action="stop", dry_run=True), fc, NOW) == 0
    out = capsys.readouterr().out
    assert fc.stopped == [] and "would-stop" in out


def test_run_stop_real_stops_idle_only_and_emails(capsys):
    idle = workspace("idle", last_used=NOW - dt.timedelta(days=3))
    busy = workspace("busy", last_used=NOW)
    fc = FakeClient(template(), [idle, busy])
    # dry_run False but no smtp.host -> emails printed, not sent
    assert am.run(cfg(action="stop", dry_run=False), fc, NOW) == 0
    out = capsys.readouterr().out
    assert fc.stopped == ["idle"]
    assert "To: user-idle@example.com" in out and "stopped (idle)" in out
    assert "notify-logged" in out
    assert "To: admin-id@example.com" in out  # template owner summary


def test_redirect_to_replaces_recipients(capsys):
    c = cfg(dry_run=True, notify={"redirect_to": "qa@example.com"})
    assert am.send_email(c, ["owner@example.com", "admin@example.com"], "s", "body\n")
    out = capsys.readouterr().out
    assert "To: qa@example.com\n" in out
    assert "[redirected: originally to owner@example.com, admin@example.com]" in out


def test_smtp_send_uses_starttls_context_and_redirect(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["host"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            sent["verify"] = context.verify_mode

        def login(self, u, p):
            sent["login"] = u

        def send_message(self, msg):
            sent["to"], sent["from"] = msg["To"], msg["From"]

    monkeypatch.setattr(am.smtplib, "SMTP", FakeSMTP)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    c = cfg(dry_run=False, notify={"redirect_to": "qa@example.com"},
            smtp={"host": "relay", "port": 25, "tls_verify": False, "from_address": "f@example.com"})
    assert am.send_email(c, ["owner@example.com"], "s", "b\n")
    assert sent == {"host": ("relay", 25), "verify": am.ssl.CERT_NONE, "to": "qa@example.com", "from": "f@example.com"}
    c["smtp"]["tls_verify"] = True
    am.send_email(c, ["owner@example.com"], "s", "b\n")
    assert sent["verify"] == am.ssl.CERT_REQUIRED


def test_run_skips_prebuilds_and_stopped():
    ws = [workspace("pb", prebuild=True, last_used=NOW - dt.timedelta(days=3)),
          workspace("st", status="stopped", last_used=NOW - dt.timedelta(days=3))]
    fc = FakeClient(template(), ws)
    assert am.run(cfg(action="stop", dry_run=False), fc, NOW) == 0
    assert fc.stopped == []


def test_run_partial_failure_exit_code():
    fc = FakeClient(template(), [workspace(last_used=NOW - dt.timedelta(days=3))], fail_stop=True)
    assert am.run(cfg(action="stop", dry_run=False), fc, NOW) == 2


# ------------------------------------------------------------------ ignore_required_stop_day

def icfg(**over):
    return cfg(ignore_required_stop_day=True, max_running_hours=72, **over)


def test_interval_mode_ignores_clamped_max_deadline():
    clamped = NOW + dt.timedelta(hours=2)
    ws = workspace(deadline=clamped, max_deadline=clamped, started=NOW - dt.timedelta(hours=10))
    rec = am.classify(ws, template(), QH_LONDON, icfg(), NOW)
    assert rec["flags"] == []  # no off_schedule / imminent_stop from Coder's deadline
    assert rec["stop_at"] == NOW + dt.timedelta(hours=62)


def test_interval_mode_imminent_and_over_interval():
    rec = am.classify(workspace(started=NOW - dt.timedelta(hours=70)), template(), QH_LONDON, icfg(), NOW)
    assert rec["flags"] == ["imminent_stop"]
    rec = am.classify(workspace(started=NOW - dt.timedelta(hours=73)), template(), QH_LONDON, icfg(), NOW)
    assert rec["flags"] == ["over_interval"] and "allowed 3d0h" in rec["reasons"][0]


def test_interval_mode_falls_back_to_build_created_at():
    ws = workspace()
    ws["latest_build"].pop("job")
    ws["latest_build"]["created_at"] = iso(NOW - dt.timedelta(hours=80))
    assert "over_interval" in am.classify(ws, template(), QH_LONDON, icfg(), NOW)["flags"]


def test_interval_mode_stops_only_over_interval_not_idle(capsys):
    over = workspace("over", started=NOW - dt.timedelta(hours=100), last_used=NOW)
    idle = workspace("idle", started=NOW - dt.timedelta(hours=2), last_used=NOW - dt.timedelta(days=3))
    fc = FakeClient(template(days=()), [over, idle])
    assert am.run(icfg(action="stop", dry_run=False), fc, NOW) == 0
    out = capsys.readouterr()
    assert fc.stopped == ["over"]
    assert "stopped (running interval exceeded)" in out.out
    assert "WARNING" not in out.err  # template has no required stop day


def test_interval_mode_warns_when_template_still_has_requirement(capsys):
    fc = FakeClient(template(days=("sunday",)), [workspace()])
    am.run(icfg(), fc, NOW)
    assert "Coder will keep enforcing it" in capsys.readouterr().err


def test_interval_mode_dedupe_notifies_once_after_crossing():
    c = icfg(action="report_idle")
    just = am.classify(workspace(started=NOW - dt.timedelta(hours=72, minutes=10)), template(), QH_LONDON, c, NOW)
    later = am.classify(workspace(started=NOW - dt.timedelta(hours=75)), template(), QH_LONDON, c, NOW)
    assert am.should_notify(just, template(), c, NOW)
    assert not am.should_notify(later, template(), c, NOW)


def test_interval_mode_requires_max_running_hours(monkeypatch):
    monkeypatch.setenv("CODER_URL", "https://c")
    monkeypatch.setenv("CODER_TOKEN", "t")
    with pytest.raises(am.ConfigError, match="max_running_hours"):
        am.load_config("/nonexistent", {"template": "t", "ignore_required_stop_day": True})
    c = am.load_config("/nonexistent", {"template": "t", "ignore_required_stop_day": True, "max_running_hours": 336})
    assert c["ignore_required_stop_day"] is True and c["max_running_hours"] == 336.0


def test_cli_flags_parse():
    a = am.parse_args(["--ignore-required-stop-day", "--max-running-hours", "336"])
    assert a.ignore_required_stop_day is True and a.max_running_hours == 336.0
    assert am.parse_args([]).ignore_required_stop_day is None


# ------------------------------------------------------------------ stop_only_in_quiet_hours

def test_quiet_hours_window_inside_and_outside():
    qh = {"time": "14:00", "timezone": "UTC"}  # NOW is 15:00 UTC
    inside, nxt, start = am.quiet_hours_window(qh, NOW, 4)
    assert inside is True and nxt is None and start.hour == 14
    inside, nxt, _ = am.quiet_hours_window(qh, NOW, 0.5)  # 14:00-14:30 already over
    assert inside is False and nxt == dt.datetime(2026, 11, 11, 14, 0, tzinfo=am.ZoneInfo("UTC"))
    inside, nxt, _ = am.quiet_hours_window({"time": "18:00", "timezone": "UTC"}, NOW, 4)
    assert inside is False and nxt.astimezone(UTC) == dt.datetime(2026, 11, 10, 18, 0, tzinfo=UTC)


def test_quiet_hours_window_crosses_midnight():
    qh = {"time": "22:00", "timezone": "UTC"}
    assert am.quiet_hours_window(qh, dt.datetime(2026, 11, 11, 1, 30, tzinfo=UTC), 4)[0] is True
    assert am.quiet_hours_window(qh, dt.datetime(2026, 11, 11, 2, 30, tzinfo=UTC), 4)[0] is False


def test_quiet_hours_window_uses_owner_timezone():
    # Sydney is UTC+11 in November: 02:00 local == 15:00 UTC the previous day
    qh = {"time": "02:00", "timezone": "Australia/Sydney"}
    assert am.quiet_hours_window(qh, NOW, 1)[0] is True
    assert am.quiet_hours_window({"time": "02:00", "timezone": "Europe/London"}, NOW, 1)[0] is False


def test_quiet_hours_window_unknown():
    assert am.quiet_hours_window(None, NOW, 4) == (None, None, None)
    assert am.quiet_hours_window({"time": "", "timezone": "UTC"}, NOW, 4)[0] is None
    assert am.quiet_hours_window({"time": "02:00", "timezone": "Not/AZone"}, NOW, 4)[0] is None


def qcfg(**over):
    base = dict(action="stop", dry_run=False, ignore_required_stop_day=True, max_running_hours=72,
                stop_only_in_quiet_hours=True, quiet_hours_window_hours=4)
    base.update(over)
    return cfg(**base)


def test_run_stops_only_owner_inside_quiet_hours(capsys):
    just_over = NOW - dt.timedelta(hours=72, minutes=10)  # crossed the interval this run -> owner is told
    a = workspace("inside", started=just_over)
    b = workspace("outside", started=just_over)
    fc = FakeClient(template(days=()), [a, b], qh={
        "user-inside": {"time": "14:30", "timezone": "UTC"},    # 14:30-18:30, NOW 15:00 -> inside
        "user-outside": {"time": "02:00", "timezone": "UTC"},   # 02:00-06:00 -> outside
    })
    assert am.run(qcfg(), fc, NOW) == 0
    out = capsys.readouterr().out
    assert fc.stopped == ["inside"]
    assert "deferred:quiet-hours Wed 2026-11-11 02:00 UTC" in out
    assert "will stop in your quiet hours (Wed 2026-11-11 02:00 UTC)" in out
    assert "The stop was made during your quiet hours." in out


def test_run_unknown_quiet_hours_is_deferred_not_stopped(capsys):
    fc = FakeClient(template(days=()), [workspace(started=NOW - dt.timedelta(hours=100))],
                    qh={"user-ws-1": None})
    assert am.run(qcfg(), fc, NOW) == 0
    assert fc.stopped == []
    assert "deferred:quiet-hours-unknown" in capsys.readouterr().out


def test_run_idle_mode_respects_quiet_hours():
    idle = workspace("idle", last_used=NOW - dt.timedelta(days=3))
    c = cfg(action="stop", dry_run=False, stop_only_in_quiet_hours=True, quiet_hours_window_hours=4)
    fc = FakeClient(template(days=()), [idle], qh={"user-idle": {"time": "02:00", "timezone": "UTC"}})
    am.run(c, fc, NOW)
    assert fc.stopped == []
    fc = FakeClient(template(days=()), [idle], qh={"user-idle": {"time": "13:00", "timezone": "UTC"}})
    am.run(c, fc, NOW)
    assert fc.stopped == ["idle"]


def test_deferred_only_does_not_resend_template_summary(capsys):
    # Over the interval long ago (dedupe: owner already told), still outside quiet hours:
    # no owner mail and no template-owner summary on this run.
    ws = workspace(started=NOW - dt.timedelta(hours=100))
    fc = FakeClient(template(days=()), [ws], qh={"user-ws-1": {"time": "02:00", "timezone": "UTC"}})
    am.run(qcfg(), fc, NOW)
    out = capsys.readouterr().out
    assert "EMAIL" not in out and "deferred:quiet-hours" in out


def test_quiet_hours_flag_without_stop_action_changes_nothing(capsys):
    ws = workspace(started=NOW - dt.timedelta(hours=100))
    fc = FakeClient(template(days=()), [ws], qh={"user-ws-1": {"time": "02:00", "timezone": "UTC"}})
    am.run(qcfg(action="report_only"), fc, NOW)
    assert fc.stopped == [] and "deferred" not in capsys.readouterr().out


def _three_owners():
    old = NOW - dt.timedelta(hours=100)
    ws = [workspace("inside", started=old), workspace("outside", started=old), workspace("unknown", started=old)]
    qh = {"user-inside": {"time": "14:30", "timezone": "UTC"},
          "user-outside": {"time": "02:00", "timezone": "UTC"},
          "user-unknown": None}
    return ws, qh


def test_force_stops_unknown_but_not_known_outside(capsys):
    ws, qh = _three_owners()
    fc = FakeClient(template(days=()), ws, qh=qh)
    assert am.run(qcfg(force=True), fc, NOW) == 0
    out = capsys.readouterr().out
    assert sorted(fc.stopped) == ["inside", "unknown"]
    assert "stopped (force: quiet hours unknown)" in out
    assert "deferred:quiet-hours Wed 2026-11-11 02:00 UTC" in out  # known-outside still waits


def test_force_all_stops_everything_qualifying(capsys):
    ws, qh = _three_owners()
    fc = FakeClient(template(days=()), ws, qh=qh)
    assert am.run(qcfg(force_all=True), fc, NOW) == 0
    out = capsys.readouterr().out
    assert sorted(fc.stopped) == ["inside", "outside", "unknown"]
    assert "stopped (force-all: outside quiet hours)" in out
    assert "stopped (force-all: quiet hours unknown)" in out
    assert "outside your quiet hours by administrator override" in out


def test_force_all_dry_run_labels_and_does_not_stop(capsys):
    ws, qh = _three_owners()
    fc = FakeClient(template(days=()), ws, qh=qh)
    am.run(qcfg(force_all=True, dry_run=True), fc, NOW)
    assert fc.stopped == [] and "would-stop (force-all: outside quiet hours)" in capsys.readouterr().out


def test_force_never_stops_non_qualifying():
    young = workspace("young", started=NOW - dt.timedelta(hours=1))  # under max_running_hours
    fc = FakeClient(template(days=()), [young], qh={"user-young": None})
    am.run(qcfg(force_all=True), fc, NOW)
    assert fc.stopped == []


def test_force_flags_cli_and_warning(monkeypatch, capsys):
    a = am.parse_args(["--force", "--force-all"])
    assert a.force is True and a.force_all is True
    monkeypatch.setenv("CODER_URL", "https://c")
    monkeypatch.setenv("CODER_TOKEN", "t")
    c = am.load_config("/nonexistent", {"template": "t", "force": True})
    assert c["force"] is True and c["force_all"] is False
    assert "no effect" in capsys.readouterr().err


def test_quiet_hours_config_validation(monkeypatch, capsys):
    monkeypatch.setenv("CODER_URL", "https://c")
    monkeypatch.setenv("CODER_TOKEN", "t")
    base = {"template": "t", "stop_only_in_quiet_hours": True}
    with pytest.raises(am.ConfigError, match="quiet_hours_window_hours"):
        am.load_config("/nonexistent", dict(base, quiet_hours_window_hours=0))
    with pytest.raises(am.ConfigError, match="quiet_hours_window_hours"):
        am.load_config("/nonexistent", dict(base, quiet_hours_window_hours=25))
    c = am.load_config("/nonexistent", dict(base, quiet_hours_window_hours=0.25))  # 15 min < 30 min interval
    assert c["stop_only_in_quiet_hours"] is True and c["quiet_hours_window_hours"] == 0.25
    assert "may never land inside" in capsys.readouterr().err


def test_quiet_hours_cli_flags():
    a = am.parse_args(["--stop-only-in-quiet-hours", "--quiet-hours-window-hours", "3"])
    assert a.stop_only_in_quiet_hours is True and a.quiet_hours_window_hours == 3.0
    assert am.parse_args([]).stop_only_in_quiet_hours is None


# ------------------------------------------------------------------ config

def test_load_config_requires_template(tmp_path, monkeypatch):
    monkeypatch.setenv("CODER_URL", "https://c")
    monkeypatch.setenv("CODER_TOKEN", "t")
    with pytest.raises(am.ConfigError):
        am.load_config(str(tmp_path / "missing.yaml"), {})


def test_load_config_file_and_cli_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CODER_URL", "https://c/")
    monkeypatch.setenv("CODER_TOKEN", "t")
    p = tmp_path / "c.yaml"
    p.write_text("template: a\ndry_run: 'false'\naction: stop\nnotify:\n  dedupe: true\n")
    c = am.load_config(str(p), {"template": "b", "dry_run": None, "notify_all": True})
    assert c["template"] == "b" and c["dry_run"] is False and c["action"] == "stop"
    assert c["notify"]["dedupe"] is False and c["notify"]["workspace_owner"] is True
    assert c["coder_url"] == "https://c"


def test_example_config_is_valid(monkeypatch):
    monkeypatch.setenv("CODER_URL", "https://c")
    monkeypatch.setenv("CODER_TOKEN", "t")
    p = os.path.join(os.path.dirname(__file__), "..", "config.example.yaml")
    c = am.load_config(p, {})
    assert c["dry_run"] is True and c["action"] in am.ACTIONS
