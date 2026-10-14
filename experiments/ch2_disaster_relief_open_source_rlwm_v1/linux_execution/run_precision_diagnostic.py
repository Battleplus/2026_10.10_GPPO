"""Run the existing precision diagnostic without replacing its archived report."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_path = args.output.resolve()
    source_path = repo_root / "upstream_smoke" / "cpu_precision_diagnostic.py"
    archived_path = (repo_root / "reports" / "cpu-precision-diagnostic-20261014.json").resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if output_path == archived_path:
        raise ValueError("diagnostic output must not target the archived report")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    original_write_text = Path.write_text

    def write_text(self: Path, data: str, *args: Any, **kwargs: Any) -> int:
        target = output_path if self.resolve() == archived_path else self
        return original_write_text(target, data, *args, **kwargs)

    Path.write_text = write_text
    old_argv = sys.argv
    try:
        sys.argv = [str(source_path)]
        runpy.run_path(str(source_path), run_name="__main__")
    finally:
        sys.argv = old_argv
        Path.write_text = original_write_text
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
