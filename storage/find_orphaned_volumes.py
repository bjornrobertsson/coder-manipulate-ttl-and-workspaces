#!/usr/bin/env python3
"""
find_orphaned_volumes.py - Find (and optionally clean up) Kubernetes storage that
outlived its Coder workspace.

Coder only deletes what is in the workspace's Terraform state, including when dormancy
auto-deletes it. Anything else survives: StatefulSet volumeClaimTemplates,
StorageClass reclaimPolicy: Retain, pre-provisioned/external volumes,
`coder delete --orphan`.

Why not diff against `coder list`?
  * The CLI defaults to `owner:me` (needs -a); the API only returns what the
    token's RBAC can see.
  * GET /api/v2/workspaces never returns deleted workspaces (the list query always
    filters workspaces.deleted = false), so `status:deleted` comes back empty.
  * A diff turns every gap (other org, token scope, another Coder deployment on
    the same cluster, paging) into "delete this volume".

Signals, strongest first:
  1. Per-workspace lookup GET /api/v2/workspaces/{id}:
     200 -> ACTIVE, 410 -> DELETED (proof), anything else -> UNKNOWN (never deleted).
     For DELETED, ?include_deleted=true gives when / who / why from latest_build.
  2. Workspace ID from the com.coder.workspace.id label, or parsed from the name
     (coder-<uuid>-home, home-coder-<uuid>-0, ...).
  3. Released PVs, aged by status.lastPhaseTransitionTime (claimRef -> workspace ID).
  4. Whether a running pod mounts the PVC (weak alone: stopped workspaces have no pod).
  5. Stale but existing workspaces (last_used_at older than --stale-days).

The default is a read-only report. Writes need --apply, and every write is printed first.

  ./find_orphaned_volumes.py -n coder-workspaces                      # report
  ./find_orphaned_volumes.py -A --all --json                          # everything, JSON
  ./find_orphaned_volumes.py -n ws --backfill-labels --mark --apply   # label legacy PVCs, stamp annotations
  ./find_orphaned_volumes.py -n ws --delete-after-days 14 --apply     # delete after 14-day grace

Env: CODER_URL, CODER_TOKEN (or audit-token.txt), the same as the other scripts here.
Needs kubectl on PATH. Python deps: requests (tabulate optional).
The token must be able to read *all* workspaces (owner/auditor/custom role). Otherwise
lookups return 404, and those volumes stay UNKNOWN and are never deleted.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

try:
    from tabulate import tabulate
except ImportError:  # optional
    tabulate = None

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LABEL_VALUE_RE = re.compile(r"[^A-Za-z0-9_.-]")

L_WS = "com.coder.workspace.id"
L_USER_ID = "com.coder.user.id"
L_USER = "com.coder.user.username"
L_TEMPLATE = "com.coder.template.name"
L_DEPLOYMENT = "com.coder.deployment"
A_ACCESS_URL = "com.coder.access-url"
A_ORPHANED = "coder.com/orphaned-at"
A_LAST_USED = "coder.com/last-used-at"

PROBLEM_STATES = {"DELETED", "UNKNOWN", "NO_ID", "FOREIGN", "STALE"}


# ---------------------------------------------------------------- config helpers
def get_token() -> str:
    if os.path.exists("audit-token.txt"):
        with open("audit-token.txt", "r") as f:
            return f.read().strip()
    token = os.environ.get("CODER_TOKEN") or os.environ.get("CODER_SESSION_TOKEN")
    if not token:
        sys.exit("No API token found. Set CODER_TOKEN or create audit-token.txt")
    return token


def get_coder_url() -> str:
    url = os.environ.get("CODER_URL")
    if not url:
        sys.exit("CODER_URL environment variable is required")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def parse_time(value: Optional[str]) -> Optional[datetime]:
    """RFC3339 (incl. nanoseconds) or epoch seconds -> aware datetime."""
    if not value or str(value).startswith("0001-01-01"):
        return None
    value = str(value).strip()
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    value = value.replace("Z", "+00:00")
    m = re.match(r"^(.*T\d\d:\d\d:\d\d)(\.\d+)?(.*)$", value)
    if m:  # trim fractional seconds to 6 digits for Python < 3.11
        value = m.group(1) + (m.group(2) or "")[:7] + m.group(3)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def days_since(dt: Optional[datetime], now: datetime) -> Optional[float]:
    return round((now - dt).total_seconds() / 86400, 1) if dt else None


def label_value(value: Optional[str]) -> str:
    """Coerce into a valid Kubernetes label value (<=63 chars, [A-Za-z0-9_.-])."""
    return LABEL_VALUE_RE.sub("-", value or "")[:63].strip("-_.")


# ---------------------------------------------------------------- Coder API
class Coder:
    def __init__(self, url: str, token: str, timeout: int = 30):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "Coder-Session-Token": token})
        self.cache: Dict[str, Dict] = {}

    def check_auth(self) -> Dict:
        r = self.session.get(f"{self.url}/api/v2/users/me", timeout=self.timeout)
        if r.status_code != 200:
            sys.exit(f"Coder auth check failed: HTTP {r.status_code} {r.text[:200]}")
        return r.json()

    def lookup(self, ws_id: str) -> Dict:
        """ACTIVE (200), DELETED (410) or UNKNOWN (anything else; 404 can mean 'not visible')."""
        if ws_id in self.cache:
            return self.cache[ws_id]
        base = f"{self.url}/api/v2/workspaces/{ws_id}"
        try:
            r = self.session.get(base, timeout=self.timeout)
            if r.status_code == 200:
                res = {"state": "ACTIVE", "ws": r.json()}
            elif r.status_code == 410:
                d = self.session.get(base, params={"include_deleted": "true"}, timeout=self.timeout)
                res = {"state": "DELETED", "ws": d.json() if d.status_code == 200 else {}}
            else:
                res = {"state": "UNKNOWN", "ws": {}, "note": f"HTTP {r.status_code}"}
        except requests.RequestException as e:
            res = {"state": "UNKNOWN", "ws": {}, "note": f"error: {e.__class__.__name__}"}
        self.cache[ws_id] = res
        return res

    def list_ids(self) -> set:
        """Live workspace IDs visible to the token (informational cross-check only)."""
        ids, offset, limit = set(), 0, 100
        while True:
            r = self.session.get(f"{self.url}/api/v2/workspaces",
                                 params={"q": "", "limit": limit, "offset": offset}, timeout=self.timeout)
            r.raise_for_status()
            page = r.json().get("workspaces") or []
            ids.update(w["id"] for w in page)
            if len(page) < limit:
                return ids
            offset += limit


# ---------------------------------------------------------------- Kubernetes (kubectl, no extra deps)
def kubectl(args: List[str], ctx: Optional[str]) -> str:
    cmd = ["kubectl"] + (["--context", ctx] if ctx else []) + args
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {p.stderr.strip()}")
    return p.stdout


def kget(kind: str, namespaces: List[str], all_ns: bool, ctx: Optional[str]) -> List[Dict]:
    if all_ns:
        return json.loads(kubectl(["get", kind, "-A", "-o", "json"], ctx))["items"]
    items: List[Dict] = []
    for ns in namespaces:
        items += json.loads(kubectl(["get", kind, "-n", ns, "-o", "json"], ctx))["items"]
    return items


# ---------------------------------------------------------------- analysis
def workspace_id_for(meta: Dict, fallback_name: str):
    labels = meta.get("labels") or {}
    if UUID_RE.fullmatch(labels.get(L_WS, "")):
        return labels[L_WS], "label"
    m = UUID_RE.search(fallback_name or "")
    return (m.group(0), "name") if m else (None, None)


def is_foreign(meta: Dict, args, coder_host: str) -> Optional[str]:
    labels, ann = meta.get("labels") or {}, meta.get("annotations") or {}
    if args.deployment and labels.get(L_DEPLOYMENT) and labels[L_DEPLOYMENT] != args.deployment:
        return f"deployment={labels[L_DEPLOYMENT]}"
    if ann.get(A_ACCESS_URL):
        host = urlparse(ann[A_ACCESS_URL]).hostname
        if host and host != coder_host:
            return f"access-url={host}"
    return None


def enrich(rec: Dict, look: Dict, now: datetime, stale_days: Optional[int]):
    ws = look.get("ws") or {}
    rec["state"] = look["state"]
    if look.get("note"):
        rec["note"] = look["note"]
    rec["owner"] = rec.get("owner") or ws.get("owner_name")
    rec["template"] = rec.get("template") or ws.get("template_name")
    rec["workspace"] = ws.get("name")
    if look["state"] == "ACTIVE":
        rec["last_used_days"] = days_since(parse_time(ws.get("last_used_at")), now)
        rec["dormant"] = bool(ws.get("dormant_at"))
        rec["ws_status"] = (ws.get("latest_build") or {}).get("status")
        if stale_days is not None and (rec["last_used_days"] or 0) >= stale_days:
            rec["state"] = "STALE"
    elif look["state"] == "DELETED":
        lb = ws.get("latest_build") or {}
        if lb.get("transition") == "delete":
            rec["deleted_days"] = days_since(parse_time(lb.get("created_at")), now)
            rec["deleted_by"] = lb.get("initiator_name")
            rec["delete_reason"] = lb.get("reason")


def analyse(args, coder: Coder) -> List[Dict]:
    now = datetime.now(timezone.utc)
    coder_host = urlparse(coder.url).hostname
    ctx = args.context

    pvcs = kget("pvc", args.namespace, args.all_namespaces, ctx)
    pods = kget("pods", args.namespace, args.all_namespaces, ctx)
    pvs: List[Dict] = []
    if not args.skip_pvs:
        try:
            pvs = json.loads(kubectl(["get", "pv", "-o", "json"], ctx))["items"]
        except RuntimeError as e:
            print(f"Warning: cannot list PVs ({e}); use --skip-pvs to silence", file=sys.stderr)
    pv_by_name = {pv["metadata"]["name"]: pv for pv in pvs}

    mounted = set()
    for pod in pods:
        if (pod.get("status") or {}).get("phase") in ("Succeeded", "Failed"):
            continue
        for vol in (pod.get("spec") or {}).get("volumes") or []:
            claim = (vol.get("persistentVolumeClaim") or {}).get("claimName")
            if claim:
                mounted.add((pod["metadata"]["namespace"], claim))

    records: List[Dict] = []
    for pvc in pvcs:
        meta, spec, status = pvc["metadata"], pvc.get("spec") or {}, pvc.get("status") or {}
        labels, ann = meta.get("labels") or {}, meta.get("annotations") or {}
        ns, name = meta["namespace"], meta["name"]
        pv = pv_by_name.get(spec.get("volumeName") or "", {})
        rec = {
            "kind": "PVC", "namespace": ns, "name": name,
            "storage_class": spec.get("storageClassName"),
            "size": (status.get("capacity") or {}).get("storage")
            or ((spec.get("resources") or {}).get("requests") or {}).get("storage"),
            "age_days": days_since(parse_time(meta.get("creationTimestamp")), now),
            "mounted": (ns, name) in mounted,
            "pv": spec.get("volumeName"),
            "reclaim": (pv.get("spec") or {}).get("persistentVolumeReclaimPolicy"),
            "owner": labels.get(L_USER), "template": labels.get(L_TEMPLATE),
            "orphaned_days": days_since(parse_time(ann.get(A_ORPHANED)), now),
            "has_orphan_mark": A_ORPHANED in ann,
        }
        rec["workspace_id"], rec["id_source"] = workspace_id_for(meta, name)
        foreign = is_foreign(meta, args, coder_host)
        if foreign:
            rec.update(state="FOREIGN", note=foreign)
        elif not rec["workspace_id"]:
            if args.require_coder_label and labels.get("com.coder.resource") != "true":
                continue  # not a Coder volume
            rec["state"] = "NO_ID"
        else:
            enrich(rec, coder.lookup(rec["workspace_id"]), now, args.stale_days)
        records.append(rec)

    for pv in pvs:
        status = pv.get("status") or {}
        if status.get("phase") != "Released":
            continue
        spec, meta = pv.get("spec") or {}, pv["metadata"]
        claim = spec.get("claimRef") or {}
        if args.storage_class and spec.get("storageClassName") not in args.storage_class:
            continue
        if not args.all_namespaces and claim.get("namespace") not in args.namespace:
            continue
        rec = {
            "kind": "PV", "namespace": claim.get("namespace"), "name": meta["name"],
            "storage_class": spec.get("storageClassName"),
            "size": (spec.get("capacity") or {}).get("storage"),
            "age_days": days_since(parse_time(meta.get("creationTimestamp")), now),
            "released_days": days_since(parse_time(status.get("lastPhaseTransitionTime")), now),
            "reclaim": spec.get("persistentVolumeReclaimPolicy"),
            "claim": claim.get("name"), "mounted": False,
        }
        rec["workspace_id"], rec["id_source"] = workspace_id_for(meta, claim.get("name", ""))
        if rec["workspace_id"]:
            enrich(rec, coder.lookup(rec["workspace_id"]), now, args.stale_days)
            if rec["state"] in ("ACTIVE", "STALE"):
                rec["note"] = "Released, but the workspace still exists (PVC recreated?)"
        else:
            rec["state"] = "NO_ID"
        rec["state"] = "RELEASED/" + rec["state"]
        records.append(rec)

    if args.cross_check_list:
        live = coder.list_ids()
        for rec in records:
            if rec.get("workspace_id") and rec["workspace_id"] not in live and rec["state"].endswith("UNKNOWN"):
                rec["note"] = (rec.get("note", "") + "; not in workspace list either").lstrip("; ")
    return records


# ---------------------------------------------------------------- actions (dry-run unless --apply)
def plan_actions(records: List[Dict], args, coder: Coder) -> List[List[str]]:
    actions: List[List[str]] = []
    destructive = 0
    now_epoch = str(int(time.time()))

    for rec in records:
        state, ns, name = rec["state"], rec["namespace"], rec["name"]
        if rec["kind"] == "PVC":
            ws = {}
            if rec.get("workspace_id") and state in ("ACTIVE", "STALE", "DELETED"):
                ws = coder.lookup(rec["workspace_id"]).get("ws") or {}
            if args.delete_after_days is not None and state == "DELETED" and not rec["mounted"]:
                # Grace counts from Coder's delete build; falls back to our orphaned-at mark.
                age = rec.get("deleted_days")
                if age is None:
                    age = rec.get("orphaned_days")
                if age is not None and age >= args.delete_after_days:
                    actions.append(["delete", "pvc", name, "-n", ns, "--wait=false"])
                    destructive += 1
                    continue  # no point labelling/annotating a PVC we're deleting
            if args.backfill_labels and rec["id_source"] == "name" and state in ("ACTIVE", "STALE", "DELETED"):
                lbl = {L_WS: rec["workspace_id"], L_USER_ID: ws.get("owner_id"),
                       L_USER: label_value(ws.get("owner_name")), L_TEMPLATE: label_value(ws.get("template_name"))}
                actions.append(["label", "pvc", name, "-n", ns, "--overwrite"]
                               + [f"{k}={v}" for k, v in lbl.items() if v])
            if args.mark:
                if state == "DELETED" and not rec["has_orphan_mark"]:
                    actions.append(["annotate", "pvc", name, "-n", ns, f"{A_ORPHANED}={now_epoch}"])
                elif state in ("ACTIVE", "STALE"):
                    if rec["has_orphan_mark"]:
                        actions.append(["annotate", "pvc", name, "-n", ns, f"{A_ORPHANED}-"])
                    if parse_time(ws.get("last_used_at")):
                        actions.append(["annotate", "pvc", name, "-n", ns, "--overwrite",
                                        f"{A_LAST_USED}={ws['last_used_at'][:19]}Z"])
        elif rec["kind"] == "PV" and args.delete_after_days is not None:
            # Flipping a Released PV to Delete lets the CSI provisioner remove the backing disk
            # (a plain `kubectl delete pv` would leave the disk behind).
            ok = state == "RELEASED/DELETED" or (args.include_unknown_pvs and state == "RELEASED/NO_ID")
            age = rec.get("released_days")
            if ok and rec["reclaim"] == "Retain" and age is not None and age >= args.delete_after_days:
                actions.append(["patch", "pv", name, "-p", '{"spec":{"persistentVolumeReclaimPolicy":"Delete"}}'])
                destructive += 1

    if destructive > args.max_deletes:
        print(f"\nRefusing destructive actions: {destructive} exceed --max-deletes {args.max_deletes}. "
              "Review the report and raise the limit if expected.", file=sys.stderr)
        actions = [a for a in actions if a[0] not in ("delete", "patch")]
    return actions


def run_actions(actions: List[List[str]], args, out=sys.stdout):
    if not actions:
        return
    print(f"\n{'APPLYING' if args.apply else 'DRY-RUN'}: {len(actions)} action(s)", file=out)
    for a in actions:
        shown = "kubectl " + " ".join(f"'{x}'" if (" " in x or "{" in x) else x for x in a)
        if not args.apply:
            print(f"  {shown}", file=out)
            continue
        try:
            kubectl(a, args.context)
            print(f"  ok   {shown}", file=out)
        except RuntimeError as e:
            print(f"  FAIL {shown}\n       {e}", file=sys.stderr)


# ---------------------------------------------------------------- output
COLUMNS = ["state", "kind", "namespace", "name", "owner", "workspace", "template", "size",
           "age_days", "mounted", "last_used_days", "deleted_days", "released_days",
           "deleted_by", "delete_reason", "reclaim", "note"]
ORDER = {"DELETED": 0, "RELEASED/DELETED": 1, "UNKNOWN": 2, "RELEASED/UNKNOWN": 2,
         "NO_ID": 3, "RELEASED/NO_ID": 3, "FOREIGN": 4, "STALE": 5}


def print_report(records: List[Dict], show_all: bool):
    rows = [r for r in records if show_all or r["kind"] == "PV" or r["state"] in PROBLEM_STATES]
    rows.sort(key=lambda r: (ORDER.get(r["state"], 9), -(r.get("age_days") or 0)))
    table = [["" if r.get(c) is None else r.get(c) for c in COLUMNS] for r in rows]
    if not table:
        print("No orphaned, unknown or stale volumes found.")
    elif tabulate:
        print(tabulate(table, headers=COLUMNS, tablefmt="simple"))
    else:
        print("\t".join(COLUMNS))
        for row in table:
            print("\t".join(str(x) for x in row))
    counts: Dict[str, int] = {}
    for r in records:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print("\nSummary: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no volumes"))
    print("DELETED = Coder returned 410 (proof) | UNKNOWN = not visible to token / error, never deleted | "
          "NO_ID = no label or UUID in name | FOREIGN = other deployment | STALE = unused >= --stale-days")


def main():
    p = argparse.ArgumentParser(description="Find Kubernetes storage left behind by deleted Coder workspaces.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument("-n", "--namespace", action="append", default=[], help="Namespace (repeatable)")
    scope.add_argument("-A", "--all-namespaces", action="store_true")
    p.add_argument("--context", help="kubectl context")
    p.add_argument("--deployment", help="Treat volumes with a different com.coder.deployment label as FOREIGN")
    p.add_argument("--storage-class", action="append", help="Only consider Released PVs of these classes")
    p.add_argument("--require-coder-label", action="store_true",
                   help="Ignore PVCs without a workspace ID unless labelled com.coder.resource=true")
    p.add_argument("--skip-pvs", action="store_true", help="Don't read cluster-scoped PVs")
    p.add_argument("--stale-days", type=int, help="Flag existing workspaces unused for N days")
    p.add_argument("--cross-check-list", action="store_true", help="Also compare with the workspace list (info only)")
    p.add_argument("--all", action="store_true", help="Show healthy volumes too")
    p.add_argument("--json", action="store_true", help="JSON output (records + planned actions)")
    p.add_argument("--backfill-labels", action="store_true", help="Label PVCs whose workspace ID came from the name")
    p.add_argument("--mark", action="store_true", help=f"Stamp {A_ORPHANED} / {A_LAST_USED} annotations")
    p.add_argument("--delete-after-days", type=int,
                   help="Delete PVCs of workspaces deleted >= N days ago; reclaim Released PVs older than N days")
    p.add_argument("--include-unknown-pvs", action="store_true",
                   help="With --delete-after-days, also reclaim Released PVs with no workspace ID")
    p.add_argument("--max-deletes", type=int, default=10, help="Safety cap on destructive actions (default 10)")
    p.add_argument("--apply", action="store_true", help="Execute actions (default: dry-run)")
    args = p.parse_args()

    coder = Coder(get_coder_url(), get_token())
    me = coder.check_auth()
    if not args.json:
        print(f"Coder: {coder.url} as {me.get('username')} | kubectl context: {args.context or 'current'}\n")
    try:
        records = analyse(args, coder)
    except RuntimeError as e:
        sys.exit(f"kubectl failed: {e}")
    actions = plan_actions(records, args, coder)

    if args.json:
        print(json.dumps({"records": records, "actions": [["kubectl"] + a for a in actions],
                          "apply": args.apply}, indent=2, default=str))
        if args.apply:
            run_actions(actions, args, out=sys.stderr)
        return
    print_report(records, args.all)
    run_actions(actions, args)


if __name__ == "__main__":
    main()
