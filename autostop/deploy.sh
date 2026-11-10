#!/usr/bin/env bash
# Deploy the autostop-manager CronJob.
#   ./deploy.sh [-n coder] [--mode configmap|git] [--config-file config.yaml]
#               [--script-file autostop_manager.py] [--git-repo URL] [--git-ref REF]
#               [--schedule "*/30 * * * *"] [--run-now] [--kubectl-dry-run] [--kubeconfig PATH]
set -x

HERE="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE="coder"
MODE="configmap"
CONFIG_FILE="$HERE/config.example.yaml"
SCRIPT_FILE="$HERE/autostop_manager.py"
REQ_FILE="$HERE/requirements.txt"
GIT_REPO="https://github.com/bjornrobertsson/coder-manipulate-ttl-and-workspaces.git"
GIT_REF="master"
SCHEDULE="*/30 * * * *"
RUN_NOW=0
DRY=0
KUBECTL=(kubectl)

usage() { sed -n '2,6p' "$0"; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--namespace)   NAMESPACE="$2"; shift 2 ;;
    --mode)           MODE="$2"; shift 2 ;;
    --config-file)    CONFIG_FILE="$2"; shift 2 ;;
    --script-file)    SCRIPT_FILE="$2"; shift 2 ;;
    --git-repo)       GIT_REPO="$2"; shift 2 ;;
    --git-ref)        GIT_REF="$2"; shift 2 ;;
    --schedule)       SCHEDULE="$2"; shift 2 ;;
    --run-now)        RUN_NOW=1; shift ;;
    --kubectl-dry-run) DRY=1; shift ;;
    --kubeconfig)     KUBECTL+=(--kubeconfig "$2"); shift 2 ;;
    -h|--help)        usage 0 ;;
    *) echo "unknown arg: $1" >&2; usage 1 ;;
  esac
done

case "$MODE" in configmap|git) ;; *) echo "--mode must be configmap or git" >&2; exit 1 ;; esac
[ -f "$CONFIG_FILE" ] || { echo "config file not found: $CONFIG_FILE" >&2; exit 1; }
if [ "$MODE" = configmap ]; then
  [ -f "$SCRIPT_FILE" ] || { echo "script not found: $SCRIPT_FILE" >&2; exit 1; }
fi

# apply: render to stdout in dry-run mode, otherwise apply to the cluster
apply() {
  if [ "$DRY" = 1 ]; then
    echo "---"; cat
  else
    "${KUBECTL[@]}" -n "$NAMESPACE" apply -f -
  fi
}

render_configmap() { # name, then --from-file args
  local name="$1"; shift
  "${KUBECTL[@]}" create configmap "$name" -n "$NAMESPACE" "$@" --dry-run=client -o yaml
}

if [ "$DRY" = 0 ]; then
  "${KUBECTL[@]}" get namespace "$NAMESPACE" >/dev/null 2>&1 || "${KUBECTL[@]}" create namespace "$NAMESPACE"
  if ! "${KUBECTL[@]}" -n "$NAMESPACE" get secret autostop-secrets >/dev/null 2>&1; then
    echo "WARNING: secret autostop-secrets missing in $NAMESPACE; see k8s/secret.example.yaml. Jobs will fail until it exists." >&2
  fi
fi

render_configmap autostop-config --from-file=config.yaml="$CONFIG_FILE" | apply

if [ "$MODE" = configmap ]; then
  render_configmap autostop-script \
    --from-file=autostop_manager.py="$SCRIPT_FILE" \
    --from-file=requirements.txt="$REQ_FILE" | apply
  MANIFEST="$HERE/k8s/cronjob.yaml"
else
  MANIFEST="$HERE/k8s/cronjob-git.yaml"
fi

# Substitute schedule / git settings on the known default lines (keeps manifests plain YAML).
esc() { printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'; }
sed \
  -e "s|^  schedule: \".*\"|  schedule: \"$(esc "$SCHEDULE")\"|" \
  -e "s|value: \"https://github.com/bjornrobertsson/coder-manipulate-ttl-and-workspaces.git\"|value: \"$(esc "$GIT_REPO")\"|" \
  -e "s|value: \"master\"|value: \"$(esc "$GIT_REF")\"|" \
  "$MANIFEST" | apply

if [ "$RUN_NOW" = 1 ]; then
  JOB="autostop-manual-$(date +%s)"
  if [ "$DRY" = 1 ]; then
    echo "# would run: kubectl -n $NAMESPACE create job $JOB --from=cronjob/autostop-manager"
  else
    "${KUBECTL[@]}" -n "$NAMESPACE" create job "$JOB" --from=cronjob/autostop-manager
    echo "follow logs: ${KUBECTL[*]} -n $NAMESPACE logs -f job/$JOB"
  fi
fi
