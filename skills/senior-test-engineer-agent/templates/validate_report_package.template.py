#!/usr/bin/env python3
"""正式测试报告包交付前自审门禁。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TEXT_EXTENSIONS = {".html", ".md", ".json", ".yaml", ".yml", ".txt"}
ASCII_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
WINDOWS_RESERVED_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\s]')
PACKAGE_SOFT_LIMIT_BYTES = 10 * 1024 * 1024
PACKAGE_HARD_LIMIT_BYTES = 20 * 1024 * 1024
SINGLE_FILE_SOFT_LIMIT_BYTES = 2 * 1024 * 1024
SINGLE_FILE_HARD_LIMIT_BYTES = 5 * 1024 * 1024
EVIDENCE_JSON_SOFT_LIMIT_BYTES = 3 * 1024 * 1024
EVIDENCE_JSON_HARD_LIMIT_BYTES = 8 * 1024 * 1024


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add(checks: list[Check], name: str, ok: bool, detail: str = "") -> None:
    checks.append(Check(name, "PASS" if ok else "FAIL", "" if ok else detail))


def threshold(checks: list[Check], name: str, size: int, soft: int, hard: int, subject: str) -> None:
    detail = f"{subject}={size / 1024 / 1024:.2f} MB；软上限={soft / 1024 / 1024:.2f} MB；硬上限={hard / 1024 / 1024:.2f} MB"
    if size > hard:
        checks.append(Check(name, "FAIL", detail))
    elif size > soft:
        checks.append(Check(name, "WARN", detail))
    else:
        checks.append(Check(name, "PASS", detail))


def fail_detail(items: list[str], limit: int = 8) -> str:
    shown = items[:limit]
    suffix = "" if len(items) <= limit else f"；另有 {len(items) - limit} 项"
    return "；".join(shown) + suffix


def to_project_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def resolve_report_dir(root: Path, explicit: str | None, current_path: Path) -> Path:
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else root / path
    if current_path.exists():
        text = read_text(current_path)
        match = re.search(r"`(reports/final/[^`]+?)/(?:index\.md/html|index\.html|index\.md)`", text)
        if match:
            return root / match.group(1)
    raise SystemExit("无法自动识别正式报告包，请使用 --report-dir 指定。")


def check_report_dir_name(report_dir: Path, checks: list[Check]) -> None:
    name = report_dir.name
    ok = bool(ASCII_SLUG_PATTERN.match(name)) and not WINDOWS_RESERVED_CHARS_PATTERN.search(name)
    add(checks, "FORMAL_DIR_ASCII_SLUG", ok, f"正式报告包目录名必须使用 ASCII slug：{name}")


def check_required_files(report_dir: Path, checks: list[Check]) -> None:
    required = ["index.html", "index.md", "manifest.yaml", "README.md"]
    missing = [name for name in required if not (report_dir / name).is_file()]
    add(checks, "REQUIRED_ROOT_FILES", not missing, fail_detail(missing))


def check_html_links(report_dir: Path, checks: list[Check]) -> None:
    bad: list[str] = []
    for html_file in report_dir.rglob("*.html"):
        text = read_text(html_file)
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:", "javascript:", "#")):
                continue
            path_part = href.split("#", 1)[0]
            if not path_part:
                continue
            target = (html_file.parent / path_part).resolve()
            try:
                target.relative_to(report_dir.resolve())
            except ValueError:
                bad.append(f"{html_file.relative_to(report_dir).as_posix()} -> OUTSIDE:{href}")
                continue
            if not target.exists():
                bad.append(f"{html_file.relative_to(report_dir).as_posix()} -> {href}")
    add(checks, "FORMAL_HTML_LINKS", not bad, fail_detail(bad))


def check_json_parse(report_dir: Path, checks: list[Check]) -> None:
    errors: list[str] = []
    for path in report_dir.rglob("*.json"):
        try:
            json.loads(read_text(path))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.relative_to(report_dir).as_posix()}:{type(exc).__name__}")
    add(checks, "JSON_PARSE", not errors, fail_detail(errors))


def check_size_limits(report_dir: Path, checks: list[Check]) -> None:
    files = [path for path in report_dir.rglob("*") if path.is_file()]
    threshold(checks, "FORMAL_PACKAGE_SIZE_LIMIT", sum(path.stat().st_size for path in files), PACKAGE_SOFT_LIMIT_BYTES, PACKAGE_HARD_LIMIT_BYTES, "正式报告包")
    large_files = [f"{path.relative_to(report_dir).as_posix()}={path.stat().st_size / 1024 / 1024:.2f} MB" for path in files if path.stat().st_size > SINGLE_FILE_HARD_LIMIT_BYTES]
    add(checks, "FORMAL_SINGLE_FILE_SIZE_LIMIT", not large_files, fail_detail(large_files))
    evidence_dir = report_dir / "evidence"
    json_size = sum(path.stat().st_size for path in evidence_dir.rglob("*.json")) if evidence_dir.exists() else 0
    threshold(checks, "EVIDENCE_JSON_SIZE_LIMIT", json_size, EVIDENCE_JSON_SOFT_LIMIT_BYTES, EVIDENCE_JSON_HARD_LIMIT_BYTES, "evidence JSON 合计")


def check_utf8_no_bom(report_dir: Path, current_path: Path, checks: list[Check]) -> None:
    bad: list[str] = []
    paths = [p for p in report_dir.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS]
    if current_path.exists():
        paths.append(current_path)
    for path in paths:
        try:
            data = path.read_bytes()
            if data.startswith(b"\xef\xbb\xbf"):
                bad.append(path.as_posix())
            data.decode("utf-8")
        except UnicodeDecodeError:
            bad.append(f"{path.as_posix()}:非 UTF-8")
    add(checks, "UTF8_NO_BOM", not bad, fail_detail(bad))


def check_current_md(root: Path, report_dir: Path, current_path: Path, checks: list[Check]) -> None:
    add(checks, "CURRENT_MD_EXISTS", current_path.exists(), to_project_path(current_path, root))
    if not current_path.exists():
        return
    text = read_text(current_path)
    add(checks, "CURRENT_VERSION_ONLY_RULE", "一个版本一条记录" in text)
    entry = to_project_path(report_dir / "index.md", root).replace("index.md", "index.md/html")
    add(checks, "CURRENT_FORMAL_ENTRY", entry in text or to_project_path(report_dir / "index.html", root) in text, entry)


def check_manifest(root: Path, report_dir: Path, checks: list[Check]) -> None:
    manifest = report_dir / "manifest.yaml"
    add(checks, "MANIFEST_EXISTS", manifest.exists(), "manifest.yaml 不存在")
    if not manifest.exists():
        return
    text = read_text(manifest)
    add(checks, "MANIFEST_FORMAL_DIR", f"formal_report_dir: {to_project_path(report_dir, root)}" in text, to_project_path(report_dir, root))
    required = ["artifact_policy:", "git_package_soft_limit_mb:", "git_package_hard_limit_mb:", "archive_strategy:"]
    add(checks, "MANIFEST_ARTIFACT_POLICY", not [item for item in required if item not in text], "缺少 artifact_policy 必填项")


def check_no_runtime_cache(root: Path, checks: list[Check]) -> None:
    caches = list(root.rglob("__pycache__")) + list(root.rglob("*.pyc"))
    add(checks, "RUNTIME_CACHE_CLEAN", not caches, fail_detail([to_project_path(path, root) for path in caches]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验 reports/final 正式报告包和 reports/current.md。")
    parser.add_argument("--report-dir", help="正式报告包目录；不传时从 reports/current.md 自动识别。")
    parser.add_argument("--current", default="reports/current.md", help="当前有效结论入口。")
    parser.add_argument("--project-root", help="项目根目录，默认自动识别。")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式结果。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).resolve() if args.project_root else project_root()
    current_path = Path(args.current)
    current_path = current_path if current_path.is_absolute() else root / current_path
    report_dir = resolve_report_dir(root, args.report_dir, current_path).resolve()
    checks: list[Check] = []
    add(checks, "REPORT_DIR_EXISTS", report_dir.is_dir(), to_project_path(report_dir, root))
    if report_dir.is_dir():
        check_report_dir_name(report_dir, checks)
        check_required_files(report_dir, checks)
        check_html_links(report_dir, checks)
        check_json_parse(report_dir, checks)
        check_size_limits(report_dir, checks)
        check_utf8_no_bom(report_dir, current_path, checks)
        check_current_md(root, report_dir, current_path, checks)
        check_manifest(root, report_dir, checks)
    check_no_runtime_cache(root, checks)
    status = "FAIL" if any(item.status == "FAIL" for item in checks) else ("WARN" if any(item.status == "WARN" for item in checks) else "PASS")
    if args.json:
        print(json.dumps({"status": status, "checks": [item.__dict__ for item in checks]}, ensure_ascii=False, indent=2))
    else:
        print(f"REPORT_PACKAGE_GATE={status}")
        print(f"REPORT_DIR={to_project_path(report_dir, root)}")
        for item in checks:
            suffix = f" {item.detail}" if item.detail else ""
            print(f"{item.name}={item.status}{suffix}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
