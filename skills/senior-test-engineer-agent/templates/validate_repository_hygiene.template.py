#!/usr/bin/env python3
"""仓库文件卫生门禁：检查误纳管、缓存、敏感本地配置和大文件。"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


LARGE_FILE_WARN_BYTES = 10 * 1024 * 1024
LOCAL_CONFIG_PATTERNS = (
    "config/test-agent.config.local.json",
    "config/prod-agent.config.local.json",
    "config/test.json",
)


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def run_git(args: list[str], root: Path) -> list[str]:
    result = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def add(checks: list[Check], name: str, ok: bool, detail: str = "") -> None:
    checks.append(Check(name, "PASS" if ok else "FAIL", "" if ok else detail))


def warn(checks: list[Check], name: str, detail: str) -> None:
    checks.append(Check(name, "WARN", detail))


def fail_detail(items: list[str], limit: int = 12) -> str:
    shown = items[:limit]
    suffix = "" if len(items) <= limit else f"；另有 {len(items) - limit} 项"
    return "；".join(shown) + suffix


def project_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    return Path.cwd().resolve()


def main() -> int:
    root = project_root()
    checks: list[Check] = []

    tracked = run_git(["ls-files"], root)
    tracked_set = set(tracked)

    tracked_ignored = run_git(["ls-files", "-ci", "--exclude-standard"], root)
    add(checks, "TRACKED_IGNORED_FILES", not tracked_ignored, fail_detail(tracked_ignored))

    local_configs = [path for path in LOCAL_CONFIG_PATTERNS if path in tracked_set]
    add(checks, "LOCAL_CONFIG_NOT_TRACKED", not local_configs, fail_detail(local_configs))

    work_files = [path for path in tracked if path == "work" or path.startswith("work/")]
    add(checks, "WORK_DIR_NOT_TRACKED", not work_files, fail_detail(work_files))

    caches = [path for path in tracked if "__pycache__/" in path or path.endswith(".pyc") or ".pytest_cache/" in path]
    add(checks, "RUNTIME_CACHE_NOT_TRACKED", not caches, fail_detail(caches))

    large_files: list[str] = []
    for path in tracked:
        full = root / path
        if full.exists() and full.is_file() and full.stat().st_size > LARGE_FILE_WARN_BYTES:
            large_files.append(f"{path}={full.stat().st_size / 1024 / 1024:.2f} MB")
    if large_files:
        warn(checks, "LARGE_TRACKED_FILES", fail_detail(large_files))
    else:
        checks.append(Check("LARGE_TRACKED_FILES", "PASS", ""))

    status = "FAIL" if any(item.status == "FAIL" for item in checks) else ("WARN" if any(item.status == "WARN" for item in checks) else "PASS")
    print(f"REPOSITORY_HYGIENE_GATE={status}")
    for item in checks:
        suffix = f" {item.detail}" if item.detail else ""
        print(f"{item.name}={item.status}{suffix}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
