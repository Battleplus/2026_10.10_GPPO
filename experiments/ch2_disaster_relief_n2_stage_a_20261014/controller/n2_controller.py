from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import pathlib
import posixpath
import shlex
import time
from collections.abc import Callable, Mapping, Sequence


AFFINITY_MARKER = "N2_PREFLIGHT_JSON="


@dataclasses.dataclass(frozen=True)
class Budget:
    wall_seconds: int
    settlement_reserve_seconds: int
    systemd_runtime_seconds: int
    cpu_quota_percent: int
    memory_max_bytes: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "Budget":
        if raw.get("status") != "APPROVED":
            raise ValueError("BUDGET_NOT_APPROVED")
        required = (
            "wall_seconds_total_including_settlement",
            "systemd_runtime_max_seconds",
            "cpu_quota_percent",
            "cgroup_memory_max_bytes",
        )
        if any(type(raw.get(key)) is not int for key in required):
            raise ValueError("BUDGET_FIELDS_INVALID")
        reserve = raw.get("settlement_reserve_seconds")
        if type(reserve) is not int:
            raise ValueError("BUDGET_SETTLEMENT_RESERVE_INVALID")
        budget = cls(
            wall_seconds=raw[required[0]],
            settlement_reserve_seconds=reserve,
            systemd_runtime_seconds=raw[required[1]],
            cpu_quota_percent=raw[required[2]],
            memory_max_bytes=raw[required[3]],
        )
        if min(dataclasses.astuple(budget)) <= 0:
            raise ValueError("BUDGET_VALUES_MUST_BE_POSITIVE")
        if budget.settlement_reserve_seconds >= budget.wall_seconds:
            raise ValueError("BUDGET_RESERVE_EXCEEDS_WALL_LIMIT")
        if budget.systemd_runtime_seconds > budget.wall_seconds:
            raise ValueError("SYSTEMD_RUNTIME_EXCEEDS_WALL_LIMIT")
        if budget.cpu_quota_percent > 100:
            raise ValueError("CPU_QUOTA_EXCEEDS_SINGLE_CPU_CAP")
        return budget

    @property
    def wall_guard_seconds(self) -> int:
        return self.wall_seconds - self.settlement_reserve_seconds


@dataclasses.dataclass(frozen=True)
class ControllerConfig:
    package_root: pathlib.Path
    manifest_rel: str
    package_sha256: str
    expected_identity: str
    run_identity: str
    unit: str
    target_host: str
    target_user: str
    connect_host: str
    remote_root: str
    python: str
    worker_entry: str
    worker_args: tuple[str, ...]
    ssh_key_file: pathlib.Path
    known_hosts: pathlib.Path
    evidence_root: pathlib.Path
    budget: Mapping[str, object]
    authorization: Mapping[str, object]
    consumption_root: pathlib.Path


class Evidence:
    def __init__(self, root: pathlib.Path):
        root.mkdir(parents=True, exist_ok=False)
        self.root = root
        self.stream = (root / "controller-transcript.txt").open("x", encoding="utf-8", newline="\n")

    def write(self, message: str) -> None:
        self.stream.write(message)
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()


def sha256(path: pathlib.Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest().upper()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def controller_bundle_rows() -> list[tuple[str, pathlib.Path, str]]:
    root = pathlib.Path(__file__).resolve().parent
    paths = [root / "managed_stage_supervisor.py", root / "managed_runtime.py",
             root / "managed_worker_entry.py", root / "vendor" / "PROVENANCE.json"]
    paths.extend(sorted((root / "vendor").glob("*.py")))
    rows = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError("CONTROLLER_BUNDLE_FILE_INVALID:" + path.name)
        relative = path.relative_to(root).as_posix()
        rows.append((relative, path, sha256(path)))
    return rows


def controller_bundle_sha256(rows: Sequence[tuple[str, pathlib.Path, str]] | None = None) -> str:
    selected = controller_bundle_rows() if rows is None else rows
    return canonical_sha256({relative: digest for relative, _path, digest in selected})


def validate_local(config: ControllerConfig) -> tuple[Budget, list[tuple[str, pathlib.Path, str]]]:
    if not config.expected_identity or config.run_identity == "":
        raise ValueError("RUN_IDENTITY_REQUIRED")
    if config.run_identity in {
        "n2-engineering-acceptance-r2-20261013-once",
        "n2-engineering-acceptance-r2-locale-json-20261014-once",
    }:
        raise ValueError("CONSUMED_RUN_IDENTITY_FORBIDDEN")
    budget = Budget.from_mapping(config.budget)
    bundle_rows = controller_bundle_rows()
    bundle_hash = controller_bundle_sha256(bundle_rows)
    authorization = config.authorization
    controller_sha256 = sha256(pathlib.Path(__file__).resolve())
    checks = {
        "approval_status": "APPROVED",
        "one_time_execution": True,
        "identity": config.expected_identity,
        "run_identity": config.run_identity,
        "target_host": config.target_host,
        "target_user": config.target_user,
        "connect_host": config.connect_host,
        "package_sha256": config.package_sha256.upper(),
        "systemd_unit": config.unit,
        "controller_sha256": controller_sha256,
        "controller_bundle_sha256": bundle_hash,
        "budget_sha256": canonical_sha256(config.budget),
        "worker_entry": config.worker_entry,
        "worker_args": list(config.worker_args),
        "remote_root": config.remote_root,
        "consumption_root": str(config.consumption_root.resolve()),
    }
    if any(authorization.get(key) != value for key, value in checks.items()):
        raise ValueError("AUTHORIZATION_MISMATCH")
    if not authorization.get("authorization_id") or not authorization.get("approved_at"):
        raise ValueError("AUTHORIZATION_RECEIPT_INCOMPLETE")
    if not config.remote_root.startswith("/") or ".." in pathlib.PurePosixPath(config.remote_root).parts:
        raise ValueError("REMOTE_ROOT_UNSAFE")
    if not config.unit.endswith(".service") or any(ch in config.unit for ch in " /\t\n"):
        raise ValueError("SYSTEMD_UNIT_INVALID")
    if any("\x00" in arg or arg in ("--package-root", "--work-root") for arg in config.worker_args):
        raise ValueError("WORKER_ARGUMENT_OVERRIDE_FORBIDDEN")
    if config.worker_args:
        raise ValueError("MANAGED_WORKER_ARGS_UNSUPPORTED")
    package_root = config.package_root.resolve(strict=True)
    manifest_path = package_root / config.manifest_rel
    if sha256(manifest_path) != config.package_sha256.upper():
        raise ValueError("PACKAGE_MANIFEST_SHA256_MISMATCH")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("identity") != config.expected_identity:
        raise ValueError("PACKAGE_IDENTITY_MISMATCH")
    files = manifest.get("files")
    hashes = manifest.get("file_sha256")
    if not isinstance(files, list) or not isinstance(hashes, dict) or len(files) != len(set(files)):
        raise ValueError("PACKAGE_FILE_TABLE_INVALID")
    managed = manifest.get("managed_runtime")
    if not isinstance(managed, dict):
        raise ValueError("MANAGED_RUNTIME_PACKAGE_CONTRACT_REQUIRED")
    request = managed.get("resource_request")
    guard_limits = managed.get("guard_limits")
    if not isinstance(request, dict) or not isinstance(guard_limits, dict):
        raise ValueError("MANAGED_RUNTIME_CONFIGURATION_INVALID")
    if (guard_limits.get("wall_seconds_total_including_settlement") != budget.wall_seconds
            or guard_limits.get("cgroup_memory_max_bytes") != budget.memory_max_bytes
            or guard_limits.get("cpu_quota_percent") != budget.cpu_quota_percent):
        raise ValueError("MANAGED_GUARD_BUDGET_MISMATCH")
    from managed_stage_supervisor import validate_resource_request
    validate_resource_request(request)
    manifest_part = pathlib.PurePosixPath(config.manifest_rel)
    worker_part = pathlib.PurePosixPath(config.worker_entry)
    if (manifest_part.is_absolute() or ".." in manifest_part.parts or worker_part.is_absolute()
            or ".." in worker_part.parts or config.worker_entry not in files):
        raise ValueError("MANIFEST_OR_WORKER_PATH_INVALID")
    expected_paths = set(files) | {config.manifest_rel}
    observed_paths = {
        item.relative_to(package_root).as_posix()
        for item in package_root.rglob("*")
        if item.is_file()
    }
    if observed_paths != expected_paths:
        raise ValueError("PACKAGE_INVENTORY_MISMATCH")
    rows: list[tuple[str, pathlib.Path, str]] = []
    for relative in sorted(files):
        path_part = pathlib.PurePosixPath(relative)
        if path_part.is_absolute() or ".." in path_part.parts or relative not in hashes:
            raise ValueError("PACKAGE_PATH_OR_HASH_TABLE_INVALID")
        local_path = package_root.joinpath(*path_part.parts)
        if local_path.is_symlink():
            raise ValueError("PACKAGE_SYMLINK_FORBIDDEN")
        digest = sha256(local_path)
        if digest != str(hashes[relative]).upper():
            raise ValueError("PACKAGE_FILE_SHA256_MISMATCH:" + relative)
        rows.append((relative, local_path, digest))
    rows.append((config.manifest_rel, manifest_path, config.package_sha256.upper()))
    if not config.ssh_key_file.is_file() or not config.known_hosts.is_file():
        raise ValueError("SSH_REFERENCE_FILE_MISSING")
    if config.evidence_root.exists():
        raise ValueError("EVIDENCE_ROOT_ALREADY_EXISTS")
    claim_path = config.consumption_root / (hashlib.sha256(
        str(authorization["authorization_id"]).encode("utf-8")
    ).hexdigest() + ".json")
    if claim_path.exists():
        raise ValueError("AUTHORIZATION_ALREADY_CONSUMED")
    return budget, rows


def consume_authorization(config: ControllerConfig) -> pathlib.Path:
    authorization_id = str(config.authorization["authorization_id"])
    claim_path = config.consumption_root / (hashlib.sha256(authorization_id.encode("utf-8")).hexdigest() + ".json")
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "authorization_id": authorization_id,
        "run_identity": config.run_identity,
        "package_sha256": config.package_sha256.upper(),
        "controller_sha256": sha256(pathlib.Path(__file__).resolve()),
        "controller_bundle_sha256": controller_bundle_sha256(),
        "budget_sha256": canonical_sha256(config.budget),
        "consumed_at_monotonic_ns": time.monotonic_ns(),
    }
    try:
        with claim_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
    except FileExistsError as exc:
        raise ValueError("AUTHORIZATION_ALREADY_CONSUMED") from exc
    return claim_path


def parse_affinity_json(output: str) -> tuple[list[int], list[int]]:
    values = [line[len(AFFINITY_MARKER):] for line in output.splitlines() if line.startswith(AFFINITY_MARKER)]
    if len(values) != 1:
        raise ValueError("SSH_AFFINITY_JSON_MISSING_OR_DUPLICATE")
    try:
        record = json.loads(values[0])
    except json.JSONDecodeError as exc:
        raise ValueError("SSH_AFFINITY_JSON_INVALID") from exc
    if not isinstance(record, dict):
        raise ValueError("SSH_AFFINITY_RECORD_INVALID")
    affinity, cpuset = record.get("sched_affinity"), record.get("cpuset_effective")
    for values_list in (affinity, cpuset):
        if not isinstance(values_list, list) or not values_list:
            raise ValueError("SSH_AFFINITY_OR_CPUSET_EMPTY")
        if any(type(cpu) is not int or cpu < 0 for cpu in values_list) or len(set(values_list)) != len(values_list):
            raise ValueError("SSH_AFFINITY_OR_CPUSET_INVALID")
    effective = sorted(set(affinity) & set(cpuset))
    if not effective:
        raise ValueError("SSH_AFFINITY_CPUSET_DISJOINT")
    return sorted(affinity), effective


def command(client, evidence: Evidence, *, label: str, text: str, timeout: float,
            deadline: float, now: Callable[[], float] = time.monotonic,
            on_output: Callable[[str], None] | None = None,
            allow_nonzero: bool = False) -> tuple[int, str]:
    if now() >= deadline:
        raise TimeoutError("WALL_GUARD_EXPIRED_BEFORE_COMMAND:" + label)
    evidence.write(f"\nCOMMAND_BEGIN label={label}\n{text}\n")
    try:
        _stdin, stdout, _stderr = client.exec_command(text, get_pty=False, timeout=timeout)
    except BaseException:
        evidence.write(f"COMMAND_OPEN_FAILED label={label} no_retry=true\n")
        raise
    channel = stdout.channel
    output = bytearray()
    error = bytearray()
    started = now()
    while True:
        if now() >= deadline or now() - started > timeout:
            channel.close()
            evidence.write(f"COMMAND_TIMEOUT label={label} no_retry=true\n")
            raise TimeoutError("REMOTE_COMMAND_TIMEOUT:" + label)
        received = False
        if channel.recv_ready():
            block = channel.recv(65536)
            output.extend(block)
            decoded = block.decode("utf-8", "replace")
            evidence.write(decoded)
            if on_output:
                on_output(decoded)
            received = True
        if channel.recv_stderr_ready():
            block = channel.recv_stderr(65536)
            error.extend(block)
            evidence.write(block.decode("utf-8", "replace"))
            received = True
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break
        if not received:
            time.sleep(0.02)
    status = channel.recv_exit_status()
    evidence.write(f"\nCOMMAND_END label={label} exit={status}\n")
    if status and not allow_nonzero:
        raise RuntimeError(f"REMOTE_COMMAND_FAILED:{label}:{status}:{error.decode('utf-8', 'replace')[-500:]}")
    return status, output.decode("utf-8", "replace")


def _remote_preflight(config: ControllerConfig) -> str:
    py = shlex.quote(config.python)
    expected_host, expected_user = shlex.quote(config.target_host), shlex.quote(config.target_user)
    body = (
        "import json, os, pathlib, socket, subprocess; "
        "cg=[x.split('::',1)[1] for x in pathlib.Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::')]; "
        "assert len(cg)==1; cp=pathlib.Path('/sys/fs/cgroup')/cg[0].lstrip('/')/'cpuset.cpus.effective'; "
        "cpus=[]; "
        "[(cpus.extend(range(int(a), int(b)+1)) if '-' in x else cpus.append(int(x))) "
        "for x in cp.read_text().strip().split(',') for a,b in [x.split('-',1) if '-' in x else (x,x)]]; "
        "print('" + AFFINITY_MARKER + "'+json.dumps({'hostname':socket.gethostname(),'user':subprocess.check_output(['id','-un'],text=True).strip(),'sched_affinity':sorted(os.sched_getaffinity(0)),'cpuset_effective':sorted(set(cpus))},separators=(',',':')))"
    )
    return (
        "set -eu\n"
        f"test \"$(hostname)\" = {expected_host}\n"
        f"test \"$(id -un)\" = {expected_user}\n"
        f"test -x {py}\n"
        f"test ! -e {shlex.quote(config.remote_root)}\n"
        f"{py} -B -c {shlex.quote(body)}\n"
    )


def _mkdir_text(package_path: str, work_path: str) -> str:
    return (
        "set -eu\n"
        f"mkdir -m 700 -p {shlex.quote(package_path)} {shlex.quote(work_path)}\n"
        f"test -z \"$(find {shlex.quote(work_path)} -mindepth 1 -print -quit)\"\n"
    )


def _systemd_text(config: ControllerConfig, package_path: str, work_path: str,
                  budget: Budget, cpus: Sequence[int], managed: Mapping[str, object]) -> str:
    affinity = ",".join(str(cpu) for cpu in cpus)
    controller_path = posixpath.join(package_path, "managed-controller")
    supervisor = posixpath.join(controller_path, "managed_stage_supervisor.py")
    config_path = posixpath.join(work_path, "managed-supervisor-config.json")
    launch_config = {
        "package_root": package_path,
        "work_root": work_path,
        "export_root": posixpath.join(work_path, "export"),
        "controller_root": controller_path,
        "w7_infrastructure": posixpath.join(controller_path, "vendor"),
        "worker_path": posixpath.join(package_path, config.worker_entry),
        "worker_sha256": managed["worker_sha256"],
        "controller_bundle_sha256": managed["controller_bundle_sha256"],
        "worker_callable": managed.get("worker_callable", "managed_worker"),
        "resource_request": managed["resource_request"],
        "guard_limits": {**managed["guard_limits"], "cpu_quota_percent": budget.cpu_quota_percent},
        "systemd_unit": config.unit,
    }
    launch_json = json.dumps(launch_config, sort_keys=True, separators=(",", ":"))
    write_config = (
        "import pathlib; p=pathlib.Path(" + repr(config_path) + "); "
        "p.write_text(" + repr(launch_json) + ",encoding='utf-8')"
    )
    wait_code = f"""import subprocess,time
u={config.unit!r}
deadline=time.monotonic()+{budget.systemd_runtime_seconds}
show=lambda p:subprocess.check_output(['systemctl','--user','show',u,'-p',p,'--value','--no-pager'],text=True).strip()
inv=show('InvocationID')
print('N2_INVOCATION_ID='+inv,flush=True)
if len(inv)!=32: raise SystemExit('INVOCATION_ID_INVALID')
while time.monotonic()<deadline:
 state=show('ActiveState')
 if state in ('inactive','failed'): break
 time.sleep(1)
else: raise SystemExit(124)
for prop in ('InvocationID','ControlGroup','ActiveState','Result','ExecMainStatus','CPUUsageNSec','MemoryPeak'):
 print(prop+'='+show(prop))
"""
    return (
        "set -eu\n"
        f"test \"$(systemctl --user show {shlex.quote(config.unit)} -p LoadState --value --no-pager)\" = not-found\n"
        f"{shlex.quote(config.python)} -B -c {shlex.quote(write_config)}\n"
        f"systemd-run --user --unit={shlex.quote(config.unit)} --property=Type=exec "
        f"--property=Restart=no --property=KillMode=control-group --property=CPUAffinity={shlex.quote(affinity)} "
        f"--property=CPUQuota={budget.cpu_quota_percent}% --property=MemoryMax={budget.memory_max_bytes} "
        f"--property=RuntimeMaxSec={budget.systemd_runtime_seconds}s "
        f"--property=WorkingDirectory={shlex.quote(package_path)} "
        "--setenv=CUDA_VISIBLE_DEVICES= --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 "
        f"{shlex.quote(config.python)} -B {shlex.quote(supervisor)} --config {shlex.quote(config_path)}\n"
        f"{shlex.quote(config.python)} -B -c {shlex.quote(wait_code)}\n"
    )


def _managed_package_config(config: ControllerConfig, package_rows: Sequence[tuple[str, pathlib.Path, str]]) -> dict:
    manifest = json.loads((config.package_root.resolve(strict=True) / config.manifest_rel).read_text(encoding="utf-8"))
    managed = manifest["managed_runtime"]
    worker_digest = next((digest for relative, _path, digest in package_rows
                         if relative == config.worker_entry), None)
    if worker_digest is None:
        raise ValueError("MANAGED_WORKER_HASH_MISSING")
    return {**managed, "worker_sha256": worker_digest}


def _transfer(rows: Sequence[tuple[str, pathlib.Path, str]], client, evidence: Evidence, package_path: str,
              deadline: float, now: Callable[[], float]) -> None:
    sftp = client.open_sftp()
    try:
        get_channel = getattr(sftp, "get_channel", None)
        if get_channel is not None:
            get_channel().settimeout(max(1.0, deadline - now()))
        for relative, local_path, digest in rows:
            if now() >= deadline:
                raise TimeoutError("WALL_GUARD_EXPIRED_DURING_TRANSFER")
            destination = posixpath.join(package_path, *relative.split("/"))
            parent = posixpath.dirname(destination)
            try:
                sftp.mkdir(parent, mode=0o700)
            except OSError:
                sftp.stat(parent)
            sftp.put(str(local_path), destination, confirm=True)
            evidence.write(f"TRANSFER_FILE path={relative} sha256={digest}\n")
    finally:
        sftp.close()


def _verify_text(config: ControllerConfig, package_path: str,
                 rows: Sequence[tuple[str, pathlib.Path, str]]) -> str:
    expected = {relative: digest for relative, _, digest in rows}
    code = (
        "import hashlib,json,pathlib; "
        f"p=pathlib.Path({package_path!r}); expected={expected!r}; "
        "actual={r:hashlib.sha256((p/r).read_bytes()).hexdigest().upper() for r in expected}; "
        "assert actual==expected; print('PACKAGE_HASHES_VERIFIED')"
    )
    return f"set -eu\n{shlex.quote(config.python)} -B -c {shlex.quote(code)}\n"


def _parse_systemd_properties(output: str) -> dict[str, str]:
    result = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def collect_managed_receipts(client, work_path: str, destination: pathlib.Path,
                             *, invocation: str, control_group: str,
                             bundle_sha256: str, guard_limits: Mapping[str, object],
                             final_stage: str, deadline: float,
                             now: Callable[[], float] = time.monotonic) -> Mapping[str, object]:
    """Fetch and validate immutable worker/supervisor receipts and declared exports."""
    destination.mkdir(parents=True, exist_ok=False)
    sftp = client.open_sftp()
    try:
        get_channel = getattr(sftp, "get_channel", None)
        if get_channel is None:
            raise ValueError("MANAGED_SFTP_DEADLINE_UNAVAILABLE")
        channel = get_channel()
        if not callable(getattr(channel, "settimeout", None)):
            raise ValueError("MANAGED_SFTP_DEADLINE_UNAVAILABLE")

        def get_bounded(remote: str, local: pathlib.Path) -> None:
            remaining = deadline - now()
            if remaining <= 0:
                raise TimeoutError("MANAGED_COLLECTION_DEADLINE_EXPIRED")
            channel.settimeout(remaining)
            sftp.get(remote, str(local))
            if now() >= deadline:
                raise TimeoutError("MANAGED_COLLECTION_DEADLINE_EXPIRED")

        receipt_paths = {
            "worker": (posixpath.join(work_path, "managed-worker-receipt.json"),
                       destination / "managed-worker-receipt.json"),
            "supervisor": (posixpath.join(work_path, "managed-supervisor-receipt.json"),
                           destination / "managed-supervisor-receipt.json"),
        }
        receipts = {}
        receipt_hashes = {}
        for name, (remote, local) in receipt_paths.items():
            get_bounded(remote, local)
            if local.is_symlink() or not local.is_file():
                raise ValueError("MANAGED_RECEIPT_NOT_REGULAR_FILE:" + name)
            receipt_hashes[name] = sha256(local)
            value = json.loads(local.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("MANAGED_RECEIPT_NOT_OBJECT:" + name)
            receipts[name] = value

        worker = receipts["worker"]
        supervisor = receipts["supervisor"]
        if worker.get("schema") != "n2-managed-worker-receipt/1":
            raise ValueError("MANAGED_WORKER_RECEIPT_SCHEMA_INVALID")
        if supervisor.get("schema") != "n2-managed-stage-supervisor/1":
            raise ValueError("MANAGED_SUPERVISOR_RECEIPT_SCHEMA_INVALID")
        ledger = worker.get("ledger")
        if (worker.get("status") != "complete" or worker.get("settlement") != "complete"
                or worker.get("stage_server_socket_present") is not True
                or not isinstance(ledger, dict) or ledger.get("pending_calls") != 0
                or ledger.get("failed_calls") != 0):
            raise ValueError("MANAGED_WORKER_SETTLEMENT_INVALID")
        if (supervisor.get("status") != "complete"
                or supervisor.get("systemd_invocation_id") != invocation
                or supervisor.get("controller_bundle_sha256") != bundle_sha256
                or supervisor.get("stage_server_final_stage") != final_stage):
            raise ValueError("MANAGED_SUPERVISOR_RECEIPT_IDENTITY_OR_STATUS_INVALID")

        cg = supervisor.get("cgroup_configuration")
        final = supervisor.get("cgroup_final")
        if not isinstance(cg, dict) or not isinstance(final, dict):
            raise ValueError("MANAGED_CGROUP_RECEIPT_INVALID")
        cgroup_path = str(cg.get("path", ""))
        prefix = "/sys/fs/cgroup"
        if not cgroup_path.startswith(prefix + "/") or cgroup_path[len(prefix):] != control_group:
            raise ValueError("MANAGED_CGROUP_PATH_MISMATCH")
        cpuset = cg.get("cpuset_effective")
        affinity = cg.get("sched_affinity")
        quota = cg.get("cpu_quota_percent")
        memory_max = cg.get("memory_max_bytes")
        pids = final.get("pids")
        supervisor_pid = supervisor.get("supervisor_pid")
        if (not isinstance(cpuset, list) or not cpuset or not isinstance(affinity, list)
                or not affinity or not set(affinity).issubset(set(cpuset))
                or type(quota) not in (int, float)
                or (type(quota) is float and not math.isfinite(quota))
                or quota <= 0
                or quota > int(guard_limits["cpu_quota_percent"])
                or type(memory_max) is not int
                or memory_max <= 0
                or memory_max > int(guard_limits["cgroup_memory_max_bytes"])
                or type(supervisor_pid) is not int or supervisor_pid <= 0
                or not isinstance(pids, list)
                or any(type(pid) is not int or pid < 0 for pid in pids)
                or pids != [supervisor_pid]
                or any(type(cpu) is not int or cpu < 0 for cpu in cpuset)
                or len(set(cpuset)) != len(cpuset)
                or any(type(cpu) is not int or cpu < 0 for cpu in affinity)
                or len(set(affinity)) != len(affinity)):
            raise ValueError("MANAGED_CGROUP_CONFIGURATION_OR_SETTLEMENT_INVALID")
        total_cpu = supervisor.get("cgroup_cpu_seconds_total")
        peak_memory = final.get("memory_peak_bytes")
        cpu_limit = guard_limits["complete_process_cpu_seconds_total_including_descendants_and_settlement"]
        if (type(total_cpu) not in (int, float) or total_cpu < 0
                or (type(total_cpu) is float and not math.isfinite(total_cpu))
                or type(cpu_limit) not in (int, float)
                or (type(cpu_limit) is float and not math.isfinite(cpu_limit))
                or cpu_limit <= 0
                or total_cpu > cpu_limit
                or type(peak_memory) is not int
                or peak_memory < 0
                or peak_memory > guard_limits["cgroup_memory_max_bytes"]):
            raise ValueError("MANAGED_CGROUP_COUNTER_LIMIT_INVALID")

        exports = worker.get("exports")
        if worker.get("export_status") != "complete" or not isinstance(exports, list) or not exports:
            raise ValueError("MANAGED_VERIFIED_EXPORT_REQUIRED")
        for index, record in enumerate(exports):
            if not isinstance(record, dict):
                raise ValueError("MANAGED_EXPORT_RECEIPT_INVALID")
            relative = pathlib.PurePosixPath(str(record.get("path", "")))
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                raise ValueError("MANAGED_EXPORT_PATH_INVALID")
            local = destination / "exports" / pathlib.Path(*relative.parts)
            remote = posixpath.join(work_path, "export", *relative.parts)
            local.parent.mkdir(parents=True, exist_ok=True)
            get_bounded(remote, local)
            if local.is_symlink() or not local.is_file():
                raise ValueError("MANAGED_EXPORT_NOT_REGULAR_FILE")
            actual = sha256(local)
            if actual != str(record.get("sha256", "")).upper() or local.stat().st_size != record.get("bytes"):
                raise ValueError("MANAGED_EXPORT_HASH_OR_SIZE_MISMATCH")
            record["collected_sha256"] = actual

        return {
            "invocation_id": invocation,
            "status": "complete",
            "managed_supervisor": "complete",
            "controller_bundle_sha256": bundle_sha256,
            "stage_server": "complete",
            "budget_ledger": "complete",
            "settlement": "complete",
            "export": "complete",
            "cgroup": "verified",
            "receipt_sha256": receipt_hashes,
            "exports": exports,
            "systemd_control_group": control_group,
        }
    finally:
        sftp.close()


def run_controller(config: ControllerConfig, *, connect: Callable[..., object],
                   collect: Callable[[object, str, pathlib.Path], Mapping[str, object]] | None = None,
                   settle_failure: Callable[[object, str, str | None, BaseException, pathlib.Path, float], str],
                   verify_authorization: Callable[[Mapping[str, object]], bool],
                   now: Callable[[], float] = time.monotonic) -> str:
    """Execute one locally authorized controller attempt; never retries or reconnects."""
    if not verify_authorization(config.authorization):
        raise ValueError("AUTHORIZATION_SIGNATURE_OR_PROVENANCE_INVALID")
    budget, rows = validate_local(config)
    bundle_rows = controller_bundle_rows()
    transfer_rows = rows + [("managed-controller/" + name, path, digest)
                             for name, path, digest in bundle_rows]
    managed = _managed_package_config(config, rows)
    managed["controller_bundle_sha256"] = controller_bundle_sha256(bundle_rows)
    consume_authorization(config)
    client = None
    evidence = None
    started = now()
    work_deadline = started + budget.wall_guard_seconds
    total_deadline = started + budget.wall_seconds
    invocation: str | None = None
    submission_attempted = False
    try:
        evidence = Evidence(config.evidence_root)
        evidence.write(f"CONTROLLER_BEGIN identity={config.run_identity} budget_wall_s={budget.wall_seconds}\n")
        client = connect(
            hostname=config.connect_host,
            username=config.target_user,
            key_filename=str(config.ssh_key_file),
            known_hosts=str(config.known_hosts),
            allow_agent=False,
            look_for_keys=False,
            timeout=20,
            banner_timeout=20,
            auth_timeout=30,
        )
        package_path = posixpath.join(config.remote_root, "package")
        work_path = posixpath.join(config.remote_root, "work")
        _, preflight = command(client, evidence, label="preflight_identity_and_cpu_json",
                               text=_remote_preflight(config), timeout=60, deadline=work_deadline, now=now)
        _, cpus = parse_affinity_json(preflight)
        command(client, evidence, label="create_remote_roots", text=_mkdir_text(package_path, work_path),
                timeout=30, deadline=work_deadline, now=now)
        if now() >= work_deadline:
            raise TimeoutError("WALL_GUARD_EXPIRED_BEFORE_TRANSFER")
        _transfer(transfer_rows, client, evidence, package_path, work_deadline, now)
        if now() >= work_deadline:
            raise TimeoutError("WALL_GUARD_EXPIRED_AFTER_TRANSFER")
        command(client, evidence, label="verify_transferred_package", text=_verify_text(config, package_path, transfer_rows),
                timeout=60, deadline=work_deadline, now=now)
        submit_text = _systemd_text(config, package_path, work_path, budget, cpus, managed)
        submission_attempted = True

        def capture_invocation(chunk: str) -> None:
            nonlocal invocation
            for line in chunk.splitlines():
                if line.startswith("N2_INVOCATION_ID="):
                    candidate = line.partition("=")[2].strip()
                    if len(candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in candidate):
                        invocation = candidate

        status, submit_output = command(client, evidence, label="submit_once_and_observe", text=submit_text,
                                        timeout=budget.wall_guard_seconds, deadline=work_deadline,
                                        now=now, allow_nonzero=True, on_output=capture_invocation)
        invocation_rows = [line.partition("=")[2] for line in submit_output.splitlines()
                           if line.startswith("N2_INVOCATION_ID=")]
        if len(invocation_rows) == 1:
            invocation = invocation_rows[0]
        if status or len(invocation) != 32 or any(ch not in "0123456789abcdefABCDEF" for ch in invocation):
            raise RuntimeError("SUBMISSION_OR_INVOCATION_EVIDENCE_INVALID:no retry")
        properties = dict(line.split("=", 1) for line in submit_output.splitlines() if "=" in line)
        if properties.get("InvocationID") != invocation:
            raise RuntimeError("SUBMISSION_INVOCATION_MISMATCH")
        if properties.get("ActiveState") != "inactive" or properties.get("Result") != "success" or properties.get("ExecMainStatus") != "0":
            raise RuntimeError("SYSTEMD_UNIT_FAILED_OR_UNKNOWN")
        if (not properties.get("ControlGroup", "").startswith("/")
                or not properties.get("CPUUsageNSec", "").isdigit()
                or not properties.get("MemoryPeak", "").isdigit()):
            raise RuntimeError("SYSTEMD_CGROUP_READBACK_INCOMPLETE")
        final_text = (
            "set -eu\n"
            f"test \"$(systemctl --user show {shlex.quote(config.unit)} -p InvocationID --value --no-pager)\" = {shlex.quote(invocation)}\n"
            f"systemctl --user show {shlex.quote(config.unit)} --no-pager -p InvocationID -p ControlGroup -p ActiveState -p Result -p ExecMainStatus -p CPUUsageNSec -p MemoryPeak\n"
        )
        _, final_output = command(client, evidence, label="collect_same_invocation_result", text=final_text,
                                  timeout=60, deadline=work_deadline, now=now)
        final_properties = _parse_systemd_properties(final_output)
        for key in ("InvocationID", "ControlGroup", "CPUUsageNSec", "MemoryPeak"):
            if final_properties.get(key) != properties.get(key):
                raise RuntimeError("SYSTEMD_FINAL_READBACK_MISMATCH:" + key)
        if now() >= work_deadline:
            raise TimeoutError("WALL_GUARD_EXPIRED_BEFORE_COLLECTION")
        if collect is None:
            receipt = collect_managed_receipts(
                client, work_path, evidence.root / "collected", invocation=invocation,
                control_group=properties["ControlGroup"],
                bundle_sha256=managed["controller_bundle_sha256"],
                guard_limits=managed["guard_limits"],
                final_stage=managed["resource_request"]["stage_order"][-1],
                deadline=work_deadline,
                now=now,
            )
        else:
            receipt = collect(client, work_path, evidence.root / "collected")
        if now() >= work_deadline:
            raise TimeoutError("WALL_GUARD_EXPIRED_DURING_COLLECTION")
        expected_receipt = {
            "invocation_id": invocation,
            "status": "complete",
            "managed_supervisor": "complete",
            "controller_bundle_sha256": managed["controller_bundle_sha256"],
            "stage_server": "complete",
            "budget_ledger": "complete",
            "settlement": "complete",
            "export": "complete",
            "cgroup": "verified",
        }
        if not isinstance(receipt, Mapping) or any(receipt.get(k) != v for k, v in expected_receipt.items()):
            raise RuntimeError("WORKER_RECEIPT_OR_SETTLEMENT_NOT_VERIFIED")
        evidence.write(f"CONTROLLER_RESULT invocation_id={invocation} status=verified_worker_receipt\n")
        return invocation
    except BaseException as exc:
        if evidence is not None:
            evidence.write(f"FIRST_ERROR type={type(exc).__name__} detail={exc} no_retry=true reconnects=0\n")
            if submission_attempted:
                cleanup = "UNKNOWN"
                try:
                    if invocation is not None:
                        stop_text = (
                            "set -eu\n"
                            f"test \"$(systemctl --user show {shlex.quote(config.unit)} -p InvocationID --value --no-pager)\" = {shlex.quote(invocation)}\n"
                            f"systemctl --user stop {shlex.quote(config.unit)}\n"
                            f"systemctl --user show {shlex.quote(config.unit)} --no-pager -p InvocationID -p ControlGroup -p ActiveState -p Result -p ExecMainStatus -p CPUUsageNSec -p MemoryPeak\n"
                        )
                        _, stop_output = command(client, evidence, label="stop_failed_invocation_same_connection", text=stop_text,
                                                 timeout=max(1, total_deadline - now()), deadline=total_deadline, now=now)
                        stop_properties = dict(line.split("=", 1) for line in stop_output.splitlines() if "=" in line)
                        if stop_properties.get("ActiveState") != "inactive":
                            raise RuntimeError("UNIT_STOP_NOT_CONFIRMED")
                        if stop_properties.get("InvocationID") != invocation:
                            raise RuntimeError("STOPPED_UNIT_INVOCATION_MISMATCH")
                    cleanup = settle_failure(client, config.unit, invocation, exc, evidence.root, total_deadline)
                except BaseException as cleanup_exc:
                    cleanup = "UNKNOWN:" + type(cleanup_exc).__name__
                evidence.write(f"FAILURE_CLEANUP status={cleanup} invocation_id={invocation or 'UNKNOWN'}\n")
        raise
    finally:
        if client is not None:
            client.close()
        if evidence is not None:
            evidence.close()
