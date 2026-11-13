#!/usr/bin/env python3
"""
Autostop manager POC: report, notify and (optionally) stop workspaces for ONE template.

Why: saving a template autostop requirement recalculates max_deadline for running
builds from the build completion time; builds older than the last required-stop day
get clamped to now+2h and stop off-schedule with no owner notification. This script
surfaces those workspaces, emails owners / template owner, and can stop idle ones.

Self-contained (single file) so it can be shipped as a ConfigMap.
Config: YAML at CONFIG_PATH (default /config/config.yaml), overridden by CLI flags.
Secrets via env: CODER_URL, CODER_TOKEN (or CODER_SESSION_TOKEN), SMTP_USERNAME, SMTP_PASSWORD.

Exit codes: 0 ok, 1 config/API error, 2 partial failure (some stops/emails failed).
"""

import argparse
import copy
import datetime as dt
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

import requests
import yaml

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - tabulate is optional
    tabulate = None

UTC = dt.timezone.utc
ZERO_TIME = "0001-01-01T00:00:00Z"
ACTIONS = ("report_only", "report_idle", "stop")

DEFAULT_CONFIG = {
    "template": "",
    "organization": "",
    "dry_run": True,
    "action": "report_only",
    "idle_threshold_hours": 24,
    "stop_window_hours": 4,
    # How often the CronJob runs; used to avoid re-sending the same email every run.
    "run_interval_minutes": 30,
    "quiet_hours_tolerance_minutes": 5,
    # Ignore the template's required stop day / max_deadline and use ONLY
    # max_running_hours (measured from the workspace's start build) to decide
    # when a workspace has run long enough. With action=stop, only workspaces
    # past that interval are stopped (idle is reported, not acted on).
    # Coder still enforces its own max_deadline: set the template's autostop
    # requirement to none for this to be the effective policy.
    "ignore_required_stop_day": False,
    "max_running_hours": 0,
    # Only stop a workspace while its OWNER is inside their quiet hours
    # (GET /api/v2/users/{id}/quiet-hours: start time + timezone). Coder defines
    # only the start, so the window is start .. start + quiet_hours_window_hours
    # in the owner's timezone. Outside it, the stop is deferred to a later run.
    # Owners whose quiet hours can't be read are deferred, never force-stopped.
    "stop_only_in_quiet_hours": False,
    "quiet_hours_window_hours": 4,
    # Overrides for stop_only_in_quiet_hours:
    #   force:     also stop workspaces whose owner's quiet hours are UNKNOWN
    #              (owners known to be outside their quiet hours still wait)
    #   force_all: ignore quiet hours entirely; stop every qualifying workspace now
    "force": False,
    "force_all": False,
    "notify": {
        "template_owner": True,
        "workspace_owner": True,
        "dedupe": True,
        "extra_recipients": [],
        # Testing / staged rollout: send every email here instead of the real
        # recipients (original recipients are listed in the body).
        "redirect_to": "",
    },
    "smtp": {
        "host": "",
        "port": 587,
        "starttls": True,
        "tls_verify": True,  # verify the relay certificate/hostname on STARTTLS
        "from_address": "coder-autostop@example.com",
    },
    "output": "table",  # table | json
}


class ConfigError(Exception):
    pass


# --------------------------------------------------------------------------- config

def deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def str2bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def load_config(path=None, cli=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    path = path or os.environ.get("CONFIG_PATH", "/config/config.yaml")
    if path and os.path.exists(path):
        with open(path) as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    cli = cli or {}
    for key in ("template", "organization", "action", "output"):
        if cli.get(key):
            cfg[key] = cli[key]
    if cli.get("dry_run") is not None:
        cfg["dry_run"] = cli["dry_run"]
    if cli.get("notify_all"):
        cfg["notify"]["dedupe"] = False
    if cli.get("ignore_required_stop_day"):
        cfg["ignore_required_stop_day"] = True
    if cli.get("max_running_hours") is not None:
        cfg["max_running_hours"] = cli["max_running_hours"]
    if cli.get("stop_only_in_quiet_hours"):
        cfg["stop_only_in_quiet_hours"] = True
    for key in ("force", "force_all"):
        if cli.get(key):
            cfg[key] = True
    if cli.get("quiet_hours_window_hours") is not None:
        cfg["quiet_hours_window_hours"] = cli["quiet_hours_window_hours"]

    cfg["dry_run"] = str2bool(cfg["dry_run"])
    cfg["ignore_required_stop_day"] = str2bool(cfg["ignore_required_stop_day"])
    try:
        cfg["max_running_hours"] = float(cfg["max_running_hours"] or 0)
    except (TypeError, ValueError):
        raise ConfigError("max_running_hours must be a number, got %r" % cfg["max_running_hours"])
    if cfg["ignore_required_stop_day"] and cfg["max_running_hours"] <= 0:
        raise ConfigError("ignore_required_stop_day requires max_running_hours > 0")
    cfg["stop_only_in_quiet_hours"] = str2bool(cfg["stop_only_in_quiet_hours"])
    cfg["force"] = str2bool(cfg["force"])
    cfg["force_all"] = str2bool(cfg["force_all"])
    if (cfg["force"] or cfg["force_all"]) and not cfg["stop_only_in_quiet_hours"]:
        print("WARNING: force/force_all only change stop_only_in_quiet_hours behaviour, which is off; "
              "they have no effect.", file=sys.stderr)
    try:
        cfg["quiet_hours_window_hours"] = float(cfg["quiet_hours_window_hours"])
    except (TypeError, ValueError):
        raise ConfigError("quiet_hours_window_hours must be a number, got %r" % cfg["quiet_hours_window_hours"])
    if cfg["stop_only_in_quiet_hours"]:
        if not 0 < cfg["quiet_hours_window_hours"] <= 24:
            raise ConfigError("quiet_hours_window_hours must be > 0 and <= 24")
        if float(cfg["run_interval_minutes"]) > cfg["quiet_hours_window_hours"] * 60:
            print("WARNING: run_interval_minutes (%s) is longer than quiet_hours_window_hours (%s h); "
                  "a run may never land inside an owner's quiet hours." % (
                      cfg["run_interval_minutes"], cfg["quiet_hours_window_hours"]), file=sys.stderr)
    if not cfg["template"]:
        raise ConfigError("'template' is required (config file or --template)")
    if cfg["action"] not in ACTIONS:
        raise ConfigError("action must be one of %s, got %r" % (ACTIONS, cfg["action"]))
    cfg["coder_url"] = (os.environ.get("CODER_URL") or "").rstrip("/")
    cfg["coder_token"] = (os.environ.get("CODER_TOKEN") or os.environ.get("CODER_SESSION_TOKEN") or "").strip()
    if not cfg["coder_token"] and os.path.exists("audit-token.txt"):
        with open("audit-token.txt") as f:
            cfg["coder_token"] = f.read().strip()
    if not cfg["coder_url"] or not cfg["coder_token"]:
        raise ConfigError("CODER_URL and CODER_TOKEN must be set")
    return cfg


# --------------------------------------------------------------------------- time helpers

def parse_time(value):
    if not value or value == ZERO_TIME:
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.year <= 1:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def fmt_delta(delta):
    if delta is None:
        return "N/A"
    secs = int(delta.total_seconds())
    sign = "-" if secs < 0 else ""
    secs = abs(secs)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "%s%dd%dh" % (sign, d, h)
    if h:
        return "%s%dh%dm" % (sign, h, m)
    return "%s%dm" % (sign, m)


def to_tz(t, tz_name):
    if t is None:
        return None
    if ZoneInfo and tz_name:
        try:
            return t.astimezone(ZoneInfo(tz_name))
        except Exception:
            pass
    return t.astimezone(UTC)


def fmt_time(t, tz_name=None):
    if t is None:
        return "N/A"
    local = to_tz(t, tz_name)
    return local.strftime("%a %Y-%m-%d %H:%M %Z")


# --------------------------------------------------------------------------- Coder API

class CoderClient:
    def __init__(self, url, token, timeout=30):
        self.url = url
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/json", "Coder-Session-Token": token})

    def get(self, path, params=None):
        r = self.s.get(self.url + path, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def post(self, path, body):
        r = self.s.post(self.url + path, json=body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def find_template(self, name_or_id, organization=""):
        templates = self.get("/api/v2/templates")
        matches = [
            t for t in templates
            if (t["id"] == name_or_id or t["name"] == name_or_id)
            and (not organization or t.get("organization_name") == organization)
        ]
        if not matches:
            raise ConfigError("template %r not found" % name_or_id)
        if len(matches) > 1:
            orgs = sorted(t.get("organization_name", "?") for t in matches)
            raise ConfigError("template %r exists in several orgs %s; set 'organization'" % (name_or_id, orgs))
        return matches[0]

    def template_workspaces(self, template):
        out, offset, limit = [], 0, 100
        q = "template:%s" % template["name"]
        while True:
            page = self.get("/api/v2/workspaces", {"q": q, "limit": limit, "offset": offset})
            batch = page.get("workspaces") or []
            out.extend(batch)
            offset += len(batch)
            if not batch or offset >= page.get("count", 0):
                break
        # q filters by name; pin to the exact template id (names repeat across orgs)
        return [w for w in out if w.get("template_id") == template["id"]]

    def user(self, user_id):
        return self.get("/api/v2/users/%s" % user_id)

    def quiet_hours(self, user_id):
        try:
            return self.get("/api/v2/users/%s/quiet-hours" % user_id)
        except requests.HTTPError:
            return None

    def stop_workspace(self, workspace_id):
        return self.post("/api/v2/workspaces/%s/builds" % workspace_id, {"transition": "stop"})


# --------------------------------------------------------------------------- classification

def effective_stop(build):
    """Earliest non-zero of deadline / max_deadline (what the autobuild loop will act on)."""
    times = [t for t in (parse_time(build.get("deadline")), parse_time(build.get("max_deadline"))) if t]
    return min(times) if times else None


def quiet_hours_start_minutes(qh):
    """'HH:MM' from the quiet-hours response -> minutes since midnight (owner TZ)."""
    if not qh or not qh.get("time"):
        return None
    try:
        h, m = qh["time"].split(":")[:2]
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def quiet_hours_window(qh, now, window_hours):
    """
    Is `now` inside the owner's quiet hours, and when does the next window start?
    Returns (inside: bool|None, next_start: datetime|None, window_start: datetime|None).
    inside is None when the quiet hours are unknown (no response / unparsable).
    Window = [start, start + window_hours) in the owner's timezone; the previous
    day's window is also checked so windows crossing midnight work.
    """
    start_min = quiet_hours_start_minutes(qh)
    if start_min is None or ZoneInfo is None:
        return None, None, None
    try:
        tz = ZoneInfo((qh or {}).get("timezone") or "UTC")
    except Exception:
        return None, None, None
    local_now = now.astimezone(tz)
    length = dt.timedelta(hours=float(window_hours))
    for day_offset in (0, -1):
        day = (local_now + dt.timedelta(days=day_offset)).date()
        start = dt.datetime(day.year, day.month, day.day, start_min // 60, start_min % 60, tzinfo=tz)
        if start <= local_now < start + length:
            return True, None, start
    day = local_now.date()
    nxt = dt.datetime(day.year, day.month, day.day, start_min // 60, start_min % 60, tzinfo=tz)
    if nxt <= local_now:
        day = day + dt.timedelta(days=1)
        nxt = dt.datetime(day.year, day.month, day.day, start_min // 60, start_min % 60, tzinfo=tz)
    return False, nxt, None


def is_off_schedule(stop_at, template, qh, tolerance_minutes=5):
    """
    True when a max_deadline-driven stop does not land on a required day at the
    start of the owner's quiet hours, i.e. it looks like the now+2h clamp.
    Returns (bool, reason).
    """
    req = template.get("autostop_requirement") or {}
    days = [d.lower() for d in (req.get("days_of_week") or [])]
    if not days or stop_at is None:
        return False, ""
    tz_name = (qh or {}).get("timezone") or "UTC"
    local = to_tz(stop_at, tz_name)
    weekday = local.strftime("%A").lower()
    if weekday not in days:
        return True, "stop on %s, template requires %s" % (weekday, ",".join(days))
    # Quiet-hours max_deadlines come from a cron schedule and are minute-aligned;
    # the now+2h clamp (enterprise/coderd/schedule/template.go) keeps the
    # seconds/microseconds of "now".
    if stop_at.second or stop_at.microsecond:
        return True, "stop at %s is not on a quiet-hours boundary (now+2h clamp)" % local.strftime("%H:%M:%S")
    qh_start = quiet_hours_start_minutes(qh)
    if qh_start is not None:
        minutes = local.hour * 60 + local.minute
        diff = min(abs(minutes - qh_start), 1440 - abs(minutes - qh_start))
        if diff > tolerance_minutes:
            return True, "stop at %s, owner quiet hours start %s %s" % (local.strftime("%H:%M"), qh["time"], tz_name)
    return False, ""


def build_started_at(lb):
    """When the current (start) build finished; falls back to build creation."""
    return parse_time((lb.get("job") or {}).get("completed_at")) or parse_time(lb.get("created_at"))


def classify(ws, template, qh, cfg, now):
    lb = ws.get("latest_build") or {}
    max_deadline = parse_time(lb.get("max_deadline"))
    last_used = parse_time(ws.get("last_used_at"))
    window = dt.timedelta(hours=float(cfg["stop_window_hours"]))
    idle_after = dt.timedelta(hours=float(cfg["idle_threshold_hours"]))
    interval_mode = cfg.get("ignore_required_stop_day")
    started = build_started_at(lb)

    flags, reasons = [], []
    if interval_mode:
        # Only our running interval counts; Coder deadline/max_deadline are ignored.
        stop_at = started + dt.timedelta(hours=float(cfg["max_running_hours"])) if started else None
        if stop_at and now >= stop_at:
            flags.append("over_interval")
            reasons.append("running %s, allowed %s" % (
                fmt_delta(now - started), fmt_delta(dt.timedelta(hours=float(cfg["max_running_hours"])))))
    else:
        stop_at = effective_stop(lb)
    if stop_at and now < stop_at <= now + window:
        flags.append("imminent_stop")
    if (not interval_mode and max_deadline and now < max_deadline <= now + window
            and stop_at == max_deadline):
        off, why = is_off_schedule(max_deadline, template, qh, cfg["quiet_hours_tolerance_minutes"])
        if off:
            flags.append("off_schedule")
            reasons.append(why)
    if last_used and now - last_used >= idle_after:
        flags.append("idle")
        reasons.append("last used %s ago" % fmt_delta(now - last_used))

    return {
        "id": ws["id"],
        "owner_id": ws["owner_id"],
        "owner": ws["owner_name"],
        "name": ws["name"],
        "status": lb.get("status"),
        "deadline": parse_time(lb.get("deadline")),
        "max_deadline": max_deadline,
        "started": started,
        "stop_at": stop_at,
        "until_stop": (stop_at - now) if stop_at else None,
        "last_used": last_used,
        "flags": flags,
        "reasons": reasons,
        "timezone": (qh or {}).get("timezone") or "UTC",
        "quiet_hours": qh,
    }


def should_notify(rec, template, cfg, now):
    """
    Dedupe for a CronJob that runs every run_interval_minutes without state:
    notify only on the run where a condition first becomes true.
    """
    if not cfg["notify"].get("dedupe", True):
        return bool({"imminent_stop", "idle", "over_interval"} & set(rec["flags"]))
    interval = dt.timedelta(minutes=float(cfg["run_interval_minutes"]))
    window = dt.timedelta(hours=float(cfg["stop_window_hours"]))
    if "over_interval" in rec["flags"] and rec["stop_at"] and now - rec["stop_at"] < interval:
        return True  # just went over the allowed running interval
    if "imminent_stop" in rec["flags"]:
        if rec["stop_at"] > now + window - interval:
            return True  # just entered the window
        tpl_updated = parse_time(template.get("updated_at"))
        if tpl_updated and tpl_updated > now - interval:
            return True  # template saved recently -> deadlines may have been clamped
    if "idle" in rec["flags"] and rec["last_used"]:
        idle_after = dt.timedelta(hours=float(cfg["idle_threshold_hours"]))
        if now - rec["last_used"] < idle_after + interval:
            return True  # just became idle
    return False


# --------------------------------------------------------------------------- email

def render_owner_email(rec, template, cfg, coder_url, stopped=False, deferred_until=None):
    tz = rec["timezone"]
    lines = ["Hello %s," % rec["owner"], ""]
    why = stop_reason(cfg)
    if stopped:
        lines.append("Your workspace '%s' (template '%s') has been stopped because %s." % (
            rec["name"], template["name"], "it was idle" if why == "idle" else "it ran longer than the allowed interval"))
        if cfg.get("stop_only_in_quiet_hours"):
            lines.append("The stop was made outside your quiet hours by administrator override."
                         if rec.get("forced") else "The stop was made during your quiet hours.")
    elif deferred_until is not None:
        lines.append("Your workspace '%s' (template '%s') %s and will be stopped during your quiet hours, "
                     "from %s." % (rec["name"], template["name"],
                                   "is idle" if why == "idle" else "has run longer than the allowed interval",
                                   fmt_time(deferred_until, tz) if deferred_until else "your next quiet hours"))
        lines.append("Save your work before then.")
    elif "over_interval" in rec["flags"]:
        lines.append("Your workspace '%s' (template '%s') has run longer than the allowed %s." % (
            rec["name"], template["name"], fmt_delta(dt.timedelta(hours=float(cfg["max_running_hours"])))))
        lines.append("Save your work; it may be stopped.")
    else:
        lines.append("Your workspace '%s' (template '%s') is scheduled to stop at %s (in %s)." % (
            rec["name"], template["name"], fmt_time(rec["stop_at"], tz), fmt_delta(rec["until_stop"])))
        lines.append("Save your work before then.")
    if rec["reasons"]:
        lines += ["", "Details:"] + ["  - %s" % r for r in rec["reasons"]]
    lines += ["", "Workspace: %s/@%s/%s" % (coder_url, rec["owner"], rec["name"])]
    if stopped:
        state = "stopped (%s)" % ("idle" if why == "idle" else "running interval exceeded")
    elif deferred_until is not None:
        state = "will stop in your quiet hours" + (" (%s)" % fmt_time(deferred_until, tz) if deferred_until else "")
    elif "over_interval" in rec["flags"]:
        state = "exceeded its running interval"
    else:
        state = "will stop at " + fmt_time(rec["stop_at"], tz)
    subject = "[Coder] Workspace %s %s" % (rec["name"], state)
    return subject, "\n".join(lines) + "\n"


def stop_reason(cfg):
    """Flag that makes action=stop stop a workspace."""
    return "over_interval" if cfg.get("ignore_required_stop_day") else "idle"


def render_template_owner_email(template, records, actions, cfg):
    lines = [
        "Autostop report for template '%s' (dry_run=%s, action=%s)" % (template["name"], cfg["dry_run"], cfg["action"]),
        "Autostop requirement: %s%s" % (
            json.dumps(template.get("autostop_requirement")),
            " (IGNORED: using max_running_hours=%s)" % cfg["max_running_hours"] if cfg.get("ignore_required_stop_day") else ""),
        "",
    ]
    for r in records:
        if not r["flags"]:
            continue
        lines.append("- %s/%s: stop %s (in %s) flags=%s %s %s" % (
            r["owner"], r["name"], fmt_time(r["stop_at"]), fmt_delta(r["until_stop"]),
            ",".join(r["flags"]), "; ".join(r["reasons"]), actions.get(r["id"], "")))
    subject = "[Coder] Autostop report: %s (%d flagged)" % (template["name"], sum(1 for r in records if r["flags"]))
    return subject, "\n".join(lines) + "\n"


def send_email(cfg, to_addrs, subject, body):
    to_addrs = [a for a in to_addrs if a]
    if not to_addrs:
        return False
    redirect = (cfg["notify"].get("redirect_to") or "").strip()
    if redirect:
        body = "[redirected: originally to %s]\n\n%s" % (", ".join(to_addrs), body)
        to_addrs = [redirect]
    if cfg["dry_run"] or not cfg["smtp"].get("host"):
        print("---- EMAIL (%s) ----\nTo: %s\nSubject: %s\n\n%s---- END EMAIL ----" % (
            "dry-run" if cfg["dry_run"] else "no smtp.host", ", ".join(to_addrs), subject, body))
        return True
    msg = EmailMessage()
    msg["From"] = cfg["smtp"]["from_address"]
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(cfg["smtp"]["host"], int(cfg["smtp"]["port"]), timeout=30) as s:
        if cfg["smtp"].get("starttls"):
            ctx = ssl.create_default_context()
            if not str2bool(cfg["smtp"].get("tls_verify", True)):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            s.starttls(context=ctx)
        user, pw = os.environ.get("SMTP_USERNAME"), os.environ.get("SMTP_PASSWORD")
        if user:
            s.login(user, pw or "")
        s.send_message(msg)
    return True


# --------------------------------------------------------------------------- output

def print_report(template, records, actions, cfg):
    if cfg["output"] == "json":
        def ser(v):
            if isinstance(v, dt.datetime):
                return v.isoformat()
            if isinstance(v, dt.timedelta):
                return v.total_seconds()
            return v
        print(json.dumps({
            "template": template["name"],
            "autostop_requirement": template.get("autostop_requirement"),
            "dry_run": cfg["dry_run"],
            "action": cfg["action"],
            "workspaces": [dict({k: ser(v) for k, v in r.items()}, action=actions.get(r["id"], "")) for r in records],
        }, indent=2))
        return
    print("Template: %s  autostop_requirement=%s  dry_run=%s  action=%s" % (
        template["name"], json.dumps(template.get("autostop_requirement")), cfg["dry_run"], cfg["action"]))
    headers = ["Owner", "Workspace", "Status", "Deadline", "Max deadline", "Until stop", "Last used", "Flags", "Action"]
    rows = [[
        r["owner"], r["name"], r["status"], fmt_time(r["deadline"]), fmt_time(r["max_deadline"]),
        fmt_delta(r["until_stop"]), fmt_time(r["last_used"]), ",".join(r["flags"]) or "-", actions.get(r["id"], "-"),
    ] for r in records]
    if tabulate:
        print(tabulate(rows, headers=headers, tablefmt="github"))
    else:
        for row in [headers] + rows:
            print(" | ".join(str(c) for c in row))


# --------------------------------------------------------------------------- main

def run(cfg, client, now=None):
    now = now or dt.datetime.now(UTC)
    template = client.find_template(cfg["template"], cfg.get("organization", ""))
    workspaces = [
        w for w in client.template_workspaces(template)
        if (w.get("latest_build") or {}).get("status") == "running" and not w.get("is_prebuild")
    ]

    if cfg.get("ignore_required_stop_day") and (template.get("autostop_requirement") or {}).get("days_of_week"):
        print("WARNING: ignore_required_stop_day is set but template %r still has an autostop requirement %s; "
              "Coder will keep enforcing it (max_deadline). Set the template's required stop days to none "
              "to make max_running_hours the effective policy." % (
                  template["name"], json.dumps(template["autostop_requirement"])), file=sys.stderr)

    users, qhs = {}, {}
    records = []
    for ws in workspaces:
        oid = ws["owner_id"]
        if oid not in qhs:
            qhs[oid] = client.quiet_hours(oid)
        records.append(classify(ws, template, qhs[oid], cfg, now))
    records.sort(key=lambda r: (r["stop_at"] or dt.datetime.max.replace(tzinfo=UTC), r["owner"], r["name"]))

    def email_of(user_id):
        if user_id not in users:
            try:
                users[user_id] = client.user(user_id).get("email", "")
            except requests.HTTPError:
                users[user_id] = ""
        return users[user_id]

    failures = 0
    actions = {}
    notify_owner = cfg["action"] in ("report_idle", "stop") and cfg["notify"].get("workspace_owner")

    for rec in records:
        stopped = False
        deferred_until = None  # None = not deferred; False = deferred, next window unknown
        if cfg["action"] == "stop" and stop_reason(cfg) in rec["flags"] and cfg.get("stop_only_in_quiet_hours"):
            inside, next_start, _ = quiet_hours_window(rec["quiet_hours"], now, cfg["quiet_hours_window_hours"])
            if not inside and cfg.get("force_all"):
                rec["forced"] = "force-all: %s" % ("outside quiet hours" if inside is False else "quiet hours unknown")
            elif inside is None and cfg.get("force"):
                rec["forced"] = "force: quiet hours unknown"
            if not inside and not rec.get("forced"):
                deferred_until = next_start if next_start else False
                actions[rec["id"]] = ("deferred:quiet-hours %s" % fmt_time(next_start, rec["timezone"])
                                      if next_start else "deferred:quiet-hours-unknown")
                rec["reasons"].append("outside owner quiet hours" if inside is False
                                      else "owner quiet hours unknown; not stopping")
        if cfg["action"] == "stop" and stop_reason(cfg) in rec["flags"] and deferred_until is None:
            if cfg["dry_run"]:
                actions[rec["id"]] = "would-stop" + (" (%s)" % rec["forced"] if rec.get("forced") else "")
            else:
                try:
                    client.stop_workspace(rec["id"])
                    actions[rec["id"]] = "stopped" + (" (%s)" % rec["forced"] if rec.get("forced") else "")
                    stopped = True
                except requests.HTTPError as e:
                    actions[rec["id"]] = "stop-failed:%s" % e.response.status_code
                    failures += 1
        if notify_owner and (stopped or should_notify(rec, template, cfg, now)):
            subject, body = render_owner_email(rec, template, cfg, cfg["coder_url"], stopped=stopped,
                                               deferred_until=deferred_until)
            try:
                if send_email(cfg, [email_of(rec["owner_id"])], subject, body):
                    if cfg["dry_run"]:
                        label = "would-notify"
                    elif not cfg["smtp"].get("host"):
                        label = "notify-logged"  # printed only, no SMTP configured
                    else:
                        label = "notified"
                    actions[rec["id"]] = (actions.get(rec["id"], "") + " " + label).strip()
            except (smtplib.SMTPException, OSError) as e:
                print("email to %s failed: %s" % (rec["owner"], e), file=sys.stderr)
                failures += 1

    print_report(template, records, actions, cfg)

    flagged = [r for r in records if r["flags"]]
    if flagged and cfg["action"] in ("report_idle", "stop") and cfg["notify"].get("template_owner"):
        # A workspace that is only "deferred" (no stop, no owner email this run) must not
        # re-trigger the summary on every CronJob run.
        acted = [a for a in actions.values() if a and (not a.startswith("deferred:") or "notif" in a)]
        if acted or not cfg["notify"].get("dedupe", True):
            recipients = [email_of(template["created_by_id"])] + list(cfg["notify"].get("extra_recipients") or [])
            subject, body = render_template_owner_email(template, records, actions, cfg)
            try:
                send_email(cfg, recipients, subject, body)
            except (smtplib.SMTPException, OSError) as e:
                print("template-owner email failed: %s" % e, file=sys.stderr)
                failures += 1
    return 2 if failures else 0


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="YAML config path (default $CONFIG_PATH or /config/config.yaml)")
    p.add_argument("--template")
    p.add_argument("--organization")
    p.add_argument("--action", choices=ACTIONS)
    p.add_argument("--output", choices=("table", "json"))
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    g.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    p.add_argument("--notify-all", action="store_true", help="disable dedupe (one-off runs)")
    p.add_argument("--ignore-required-stop-day", action="store_true", default=None,
                   help="ignore template required stop day/max_deadline; use only --max-running-hours")
    p.add_argument("--max-running-hours", type=float,
                   help="allowed running time since the workspace's start build (used with --ignore-required-stop-day)")
    p.add_argument("--stop-only-in-quiet-hours", action="store_true", default=None,
                   help="with --action stop: only stop while the workspace owner is inside their quiet hours")
    p.add_argument("--force", action="store_true", default=None,
                   help="with --stop-only-in-quiet-hours: also stop workspaces whose owner's quiet hours are unknown")
    p.add_argument("--force-all", action="store_true", default=None,
                   help="with --stop-only-in-quiet-hours: ignore quiet hours and stop every qualifying workspace now")
    p.add_argument("--quiet-hours-window-hours", type=float,
                   help="length of the quiet-hours window after the owner's quiet-hours start (default 4)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        cfg = load_config(args.config, vars(args))
        client = CoderClient(cfg["coder_url"], cfg["coder_token"])
        return run(cfg, client)
    except ConfigError as e:
        print("config error: %s" % e, file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print("coder API error: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
