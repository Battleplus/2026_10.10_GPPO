#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf '%s\n' 'usage: launch_systemd_run.sh --repo-root PATH --venv-path PATH --output-dir PATH --unit NAME --run-id ID --source-identity ID'
}

repo_root=
venv_path=
output_dir=
unit_name=
run_id=
source_identity=
while (($#)); do
  case "$1" in
    --repo-root) repo_root=${2-}; shift 2 ;;
    --venv-path) venv_path=${2-}; shift 2 ;;
    --output-dir) output_dir=${2-}; shift 2 ;;
    --unit) unit_name=${2-}; shift 2 ;;
    --run-id) run_id=${2-}; shift 2 ;;
    --source-identity) source_identity=${2-}; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 64 ;;
  esac
done

if [[ -z "$repo_root" || -z "$venv_path" || -z "$output_dir" || -z "$unit_name" || -z "$run_id" || -z "$source_identity" ]]; then
  usage >&2
  exit 64
fi
if [[ ! -x "$venv_path/bin/python" ]]; then
  printf 'venv Python is not executable: %s\n' "$venv_path/bin/python" >&2
  exit 66
fi
case "$run_id" in *[!A-Za-z0-9._-]*) printf 'invalid run id: %s\n' "$run_id" >&2; exit 64 ;; esac
case "$unit_name" in *[!A-Za-z0-9_.@-]*) printf 'invalid unit name: %s\n' "$unit_name" >&2; exit 64 ;; esac
case "$output_dir/" in "$repo_root/reports/linux-engineering-20261014/"*) ;; *) printf 'output dir must be under reports/linux-engineering-20261014\n' >&2; exit 64 ;; esac
if [[ -e "$output_dir/run-started.json" || -e "$output_dir/run-receipt.json" || -e "$output_dir/systemd-run.log" ]]; then
  printf 'run evidence already exists; refusing to repeat run id %s\n' "$run_id" >&2
  exit 73
fi
mkdir -p "$output_dir"

set +e
systemd-run \
  --user \
  --no-block \
  --unit="$unit_name" \
  --property=Type=exec \
  --property=RemainAfterExit=yes \
  --property=Restart=no \
  --property=KillMode=control-group \
  --property=CPUAffinity=0 \
  --property=CPUQuota=100% \
  --property=CPUAccounting=yes \
  --property=MemoryAccounting=yes \
  --property=TasksAccounting=yes \
  --property=MemoryMax=4G \
  --property=RuntimeMaxSec=600s \
  --property="WorkingDirectory=$repo_root" \
  --property="StandardOutput=file:$output_dir/runner-console.log" \
  --property=StandardError=inherit \
  --setenv=CUDA_VISIBLE_DEVICES= \
  --setenv=OMP_NUM_THREADS=1 \
  --setenv=MKL_NUM_THREADS=1 \
  --setenv=OPENBLAS_NUM_THREADS=1 \
  --setenv=NUMEXPR_NUM_THREADS=1 \
  --setenv=PYTHONDONTWRITEBYTECODE=1 \
  --setenv=PYTHONHASHSEED=8201 \
  --setenv=TOKENIZERS_PARALLELISM=false \
  "$venv_path/bin/python" -B \
  "$repo_root/linux_execution/run_linux_engineering.py" \
  run \
  --repo-root "$repo_root" \
  --venv-path "$venv_path" \
  --output-dir "$output_dir" \
  --run-id "$run_id" \
  --source-identity "$source_identity" \
  --cpu 0 \
  > "$output_dir/systemd-run.log" 2>&1
launch_rc=$?
set -e

service_rc=$launch_rc
if ((launch_rc == 0)); then
  systemctl --user show "$unit_name" --property=LoadState,InvocationID,ControlGroup,ExecMainPID,RemainAfterExit,ActiveState,SubState,Result,ExecMainStatus,Restart,KillMode,CPUAffinity,CPUQuotaPerSecUSec,MemoryMax,RuntimeMaxUSec > "$output_dir/unit-started.txt"
  deadline=$((SECONDS + 620))
  while ((SECONDS < deadline)); do
    active_state=$(systemctl --user show --property=ActiveState --value "$unit_name" 2>/dev/null || true)
    sub_state=$(systemctl --user show --property=SubState --value "$unit_name" 2>/dev/null || true)
    if [[ "$active_state" == "inactive" || "$active_state" == "failed" || ( "$active_state" == "active" && "$sub_state" == "exited" ) ]]; then
      result=$(systemctl --user show --property=Result --value "$unit_name" 2>/dev/null || true)
      exit_status=$(systemctl --user show --property=ExecMainStatus --value "$unit_name" 2>/dev/null || true)
      if [[ "$result" == "success" && "$exit_status" == "0" ]]; then
        service_rc=0
      elif [[ "$exit_status" =~ ^[0-9]+$ ]] && ((exit_status > 0)); then
        service_rc=$exit_status
      else
        service_rc=1
      fi
      break
    fi
    sleep 1
  done
  if ((SECONDS >= deadline)); then
    systemctl --user stop "$unit_name" >/dev/null 2>&1 || true
    service_rc=124
  fi
fi

set +e
"$venv_path/bin/python" -B "$repo_root/linux_execution/finalize_systemd_run.py" \
  --output-dir "$output_dir" \
  --unit "$unit_name" \
  --run-id "$run_id" \
  --service-exit-code "$service_rc" \
  --source-identity "$source_identity"
finalize_rc=$?
set -e

printf 'service_exit_code=%s\nfinalize_exit_code=%s\n' "$service_rc" "$finalize_rc"
if ((service_rc != 0)); then
  exit "$service_rc"
fi
exit "$finalize_rc"
