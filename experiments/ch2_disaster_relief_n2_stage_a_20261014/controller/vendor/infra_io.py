"""Durable JSONL append helper required by the vendored W7 ledger protocol.

The supplied W7 reference tree imports this module but does not include its
source. This compatibility implementation preserves the append and fsync
contract needed by the vendored modules.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


def durable_append_jsonl(path: Path, payload: Mapping) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
