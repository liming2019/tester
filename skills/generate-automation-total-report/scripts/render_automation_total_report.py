#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SUITES = [
    ("ui-functional", "UI 功能自动化第一批", "UI", "automation/reports/{version}/ui-functional/latest"),
    ("ui-functional-batch2", "UI 功能自动化第二批", "UI", "automation/reports/{version}/ui-functional-batch2/latest"),
    ("api", "接口自动化", "API", "automation/reports/{version}/api/latest"),
    ("ui-api-integration", "UI+接口联动自动化", "UI+API", "automation/reports/{version}/ui-api-integration/latest"),
]

STATUS_LABELS = {
    "passed": "通过",
    "failed": "失败",
    "blocked": "阻塞",
    "warning": "风险",
    "skipped": "跳过",
    "unknown": "未知",
}

STATUS_ALIASES = {
    "pass": "passed",
    "passed": "passed",
    "success": "passed",
    "ok": "passed",
    "fail": "failed",
    "failed": "failed",
    "error": "failed",
    "blocked": "blocked",
    "block": "blocked",
    "warning": "warning",
    "warn": "warning",
    "risk": "warning",
    "skipped": "skipped",
    "skip": "skipped",
}

SENSITIVE_KEYWORDS = (
    "authorization",
    "x-auth-token",
    "cookie",
    "set-cookie",
    "token",
    "password",
    "passwd",
    "secret",
    "access_token",
    "refresh_token",
    "session",
)

FORBIDDEN_HTML_SECTIONS = (
    "套件结果",
    "未闭环项",
    "查看子报告",
    "打开子报告",
    "报告质量自审",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成单页中文自动化执行总报告")
    parser.add_argument("--project-root", default=".", help="项目根目录，默认当前目录")
    parser.add_argument("--version", default="v1.1", help="版本号，例如 v1.1")
    parser.add_argument("--output-dir", default="", help="输出目录，默认 automation/reports/<version>/automation-total/latest")
    parser.add_argument("--title", default="", help="报告标题，默认 <VERSION> 自动化执行总报告")
    parser.add_argument("--active-environment", default="", help="环境名称，未传则从套件产物读取")
    parser.add_argument(
        "--suite",
        action="append",
        default=[],
        help="自定义套件，格式：suite_id|套件名称|类型|相对或绝对目录；类型建议 UI、API、UI+API",
    )
    parser.add_argument(
        "--fail-on-test-failure",
        action="store_true",
        help="存在失败用例时以非 0 状态退出；默认只负责生成报告",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def normalize_status(value: Any) -> str:
    key = str(value or "").strip().lower()
    return STATUS_ALIASES.get(key, "unknown")


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status or "未知")


def type_label(value: str) -> str:
    key = (value or "").strip().lower()
    if key in {"ui", "ui_functional", "ui-functional"}:
        return "UI"
    if key in {"api", "interface"}:
        return "API"
    if key in {"ui+api", "ui_api", "ui-api", "ui_api_integration", "integration"}:
        return "UI+API"
    return value or "未分类"


def short_text(value: Any, limit: int = 240) -> str:
    text = stringify(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(word in lower for word in SENSITIVE_KEYWORDS)


def redact(value: Any, parent_key: str = "") -> Any:
    if is_sensitive_key(parent_key):
        return "<已脱敏>"
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, parent_key) for item in value]
    if isinstance(value, str):
        text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]{12,}", r"\1<已脱敏>", value)
        text = re.sub(r"(?i)([?&](?:token|password|secret|access_token|refresh_token)=)[^&\s]+", r"\1<已脱敏>", text)
        return text
    return value


def safe_json(value: Any) -> str:
    return json.dumps(redact(value), ensure_ascii=False, indent=2)


def parse_suite_specs(raw_specs: list[str], version: str) -> list[tuple[str, str, str, str]]:
    if not raw_specs:
        return [(sid, name, stype, path.format(version=version)) for sid, name, stype, path in DEFAULT_SUITES]

    specs: list[tuple[str, str, str, str]] = []
    for raw in raw_specs:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 4:
            raise ValueError(f"--suite 格式错误：{raw}")
        specs.append((parts[0], parts[1], type_label(parts[2]), parts[3].format(version=version)))
    return specs


def resolve_dir(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return project_root / path


def extract_cases(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("cases", "results", "test_results", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def extract_environment(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("environment"), dict):
        return data["environment"]
    return {}


def resolve_artifact_path(project_root: Path, suite_dir: Path, raw_path: Any) -> tuple[str, bool]:
    if not raw_path:
        return "", False
    path_text = str(raw_path).strip()
    path = Path(path_text)
    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend([project_root / path_text, suite_dir / path_text])
        candidates.append(suite_dir / "screenshots" / path.name)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve()), True
    fallback = candidates[0] if candidates else project_root / path_text
    return str(fallback.resolve()), False


def rel_url(path_text: str, output_dir: Path) -> str:
    if not path_text:
        return ""
    try:
        return os.path.relpath(path_text, output_dir).replace("\\", "/")
    except ValueError:
        return Path(path_text).as_posix()


def assertion_counts(case: dict[str, Any]) -> tuple[int, int]:
    assertions = as_list(case.get("assertions"))
    total = case.get("assertion_total")
    passed = case.get("assertion_passed")
    if isinstance(total, int):
        assertion_total = total
    else:
        assertion_total = len([item for item in assertions if isinstance(item, dict)])
    if isinstance(passed, int):
        assertion_passed = passed
    else:
        assertion_passed = 0
        for item in assertions:
            if isinstance(item, dict) and item.get("passed") is True:
                assertion_passed += 1
    return assertion_total, assertion_passed


def normalize_case(
    case: dict[str, Any],
    suite_id: str,
    suite_name: str,
    suite_type: str,
    suite_dir: Path,
    project_root: Path,
    output_dir: Path,
    ordinal: int,
) -> dict[str, Any]:
    status = normalize_status(case.get("status") or case.get("result"))
    assertions = [item for item in as_list(case.get("assertions")) if isinstance(item, dict)]
    assertion_total, assertion_passed = assertion_counts(case)

    screenshots = []
    for shot in as_list(case.get("screenshots") or case.get("evidence") or case.get("images")):
        if isinstance(shot, dict):
            name = shot.get("name") or shot.get("title") or shot.get("label") or "截图证据"
            raw_path = shot.get("path") or shot.get("file") or shot.get("url")
        else:
            name = "截图证据"
            raw_path = shot
        abs_path, exists = resolve_artifact_path(project_root, suite_dir, raw_path)
        screenshots.append(
            {
                "name": str(name),
                "path": abs_path,
                "url": rel_url(abs_path, output_dir),
                "exists": exists,
            }
        )

    detail_type = type_label(case.get("type") or suite_type)
    if suite_type in {"UI", "API", "UI+API"}:
        detail_type = suite_type

    return {
        "ordinal": ordinal,
        "id": str(case.get("id") or case.get("case_id") or f"AUTO-TC-{ordinal:03d}"),
        "title": str(case.get("title") or case.get("name") or "未命名用例"),
        "type": detail_type,
        "status": status,
        "status_label": status_label(status),
        "suite_id": suite_id,
        "suite_name": suite_name,
        "suite_type": suite_type,
        "related_cases": [str(item) for item in as_list(case.get("related_cases") or case.get("business_case_ids"))],
        "matrix_ids": [str(item) for item in as_list(case.get("matrix_ids") or case.get("api_matrix_ids"))],
        "basis": str(case.get("basis") or case.get("test_basis") or case.get("note") or ""),
        "scope": str(case.get("scope") or case.get("category") or ""),
        "interface": str(case.get("interface") or case.get("api") or ""),
        "category": str(case.get("category") or ""),
        "steps": [str(item) for item in as_list(case.get("steps") or case.get("execution_steps"))],
        "pass_criteria": [str(item) for item in as_list(case.get("pass_criteria") or case.get("expected") or case.get("expected_results"))],
        "assertions": assertions,
        "assertion_total": assertion_total,
        "assertion_passed": assertion_passed,
        "screenshots": screenshots,
        "requests": redact(case.get("requests") or []),
        "responses": redact(case.get("responses") or []),
        "elapsed_ms": case.get("elapsed_ms"),
        "note": str(case.get("note") or ""),
        "blocked_reason": str(case.get("blocked_reason") or ""),
    }


def load_suites(project_root: Path, output_dir: Path, version: str, raw_specs: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    suite_specs = parse_suite_specs(raw_specs, version)
    suites: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    environment: dict[str, Any] = {}
    ordinal = 1

    for suite_id, suite_name, suite_type, suite_path in suite_specs:
        suite_dir = resolve_dir(project_root, suite_path)
        result_file = suite_dir / "test-results.json"
        summary_file = suite_dir / "summary.json"
        if not result_file.exists():
            suites.append(
                {
                    "suite_id": suite_id,
                    "suite_name": suite_name,
                    "suite_type": suite_type,
                    "suite_dir": str(suite_dir),
                    "loaded": False,
                    "reason": "未找到 test-results.json",
                    "total": 0,
                }
            )
            continue

        data = read_json(result_file)
        summary_data = read_json(summary_file) if summary_file.exists() else {}
        suite_cases = extract_cases(data)
        if not environment:
            environment = extract_environment(data) or extract_environment(summary_data)

        normalized = []
        for case in suite_cases:
            normalized_case = normalize_case(case, suite_id, suite_name, suite_type, suite_dir, project_root, output_dir, ordinal)
            normalized.append(normalized_case)
            cases.append(normalized_case)
            ordinal += 1

        suites.append(
            {
                "suite_id": suite_id,
                "suite_name": suite_name,
                "suite_type": suite_type,
                "suite_dir": str(suite_dir),
                "loaded": True,
                "total": len(normalized),
                "passed": sum(1 for item in normalized if item["status"] == "passed"),
                "failed": sum(1 for item in normalized if item["status"] == "failed"),
                "warning": sum(1 for item in normalized if item["status"] == "warning"),
                "blocked": sum(1 for item in normalized if item["status"] == "blocked"),
                "skipped": sum(1 for item in normalized if item["status"] == "skipped"),
                "source_summary": summary_data.get("summary") or summary_data.get("counts") if isinstance(summary_data, dict) else {},
            }
        )

    return suites, cases, environment


def build_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "total": len(cases),
        "passed": 0,
        "failed": 0,
        "warning": 0,
        "blocked": 0,
        "skipped": 0,
        "unknown": 0,
        "assertion_total": 0,
        "assertion_passed": 0,
        "screenshot_total": 0,
    }
    for case in cases:
        status = case.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        counts["assertion_total"] += int(case.get("assertion_total") or 0)
        counts["assertion_passed"] += int(case.get("assertion_passed") or 0)
        counts["screenshot_total"] += len(case.get("screenshots") or [])
    counts["core_total"] = counts["passed"] + counts["failed"]
    counts["core_passed"] = counts["passed"]
    counts["core_failed"] = counts["failed"]
    counts["pass_rate"] = round((counts["passed"] / counts["total"] * 100), 2) if counts["total"] else 0
    return counts


def conclusion(summary: dict[str, Any]) -> tuple[str, str]:
    if summary.get("failed", 0) > 0:
        return "不通过", "存在失败用例，需要研发修复或测试复核后重新执行。"
    if summary.get("blocked", 0) > 0:
        return "有阻塞", "自动化已完成可执行范围，仍有阻塞用例依赖前置数据、环境或清理策略。"
    if summary.get("warning", 0) > 0:
        return "通过但有风险", "核心断言通过，存在需评审确认的风险或观察项。"
    return "通过", "自动化用例全部通过，截图和断言证据可在用例明细中复核。"


def render_list(items: list[Any], ordered: bool = False) -> str:
    if not items:
        return '<p class="muted">未提供</p>'
    tag = "ol" if ordered else "ul"
    rows = "".join(f"<li>{esc(item)}</li>" for item in items)
    return f'<{tag} class="text-list">{rows}</{tag}>'


def render_chips(items: list[str], label: str) -> str:
    if not items:
        return ""
    chips = "".join(f'<span class="chip">{esc(item)}</span>' for item in items)
    return f'<div class="chip-line"><span class="chip-label">{esc(label)}</span>{chips}</div>'


def chip_group(items: list[str]) -> str:
    if not items:
        return '<span class="muted">未提供</span>'
    return "".join(f'<span class="chip">{esc(item)}</span>' for item in items)


def render_assertions(case: dict[str, Any]) -> str:
    assertions = case.get("assertions") or []
    if not assertions:
        reason = case.get("blocked_reason") or case.get("note") or "当前用例没有执行断言。"
        return f'<div class="empty-state">{esc(reason)}</div>'
    rows = []
    for assertion in assertions:
        passed = assertion.get("passed") is True
        result = "通过" if passed else "失败"
        result_class = "passed" if passed else "failed"
        check = assertion.get("check") or assertion.get("message") or assertion.get("name") or "断言项"
        rows.append(
            "<tr>"
            f"<td>{esc(check)}</td>"
            f"<td>{esc(short_text(assertion.get('expected'), 500))}</td>"
            f"<td>{esc(short_text(assertion.get('actual'), 700))}</td>"
            f'<td><span class="pill {result_class}">{result}</span></td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="assertion-table">'
        "<thead><tr><th>检查项</th><th>期望</th><th>实际</th><th>结果</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_screenshots(case: dict[str, Any]) -> str:
    screenshots = case.get("screenshots") or []
    if not screenshots:
        return '<div class="empty-state">未提供截图证据</div>'
    cards = []
    for shot in screenshots:
        name = shot.get("name") or "截图证据"
        url = shot.get("url") or shot.get("path") or ""
        exists = shot.get("exists")
        missing = "" if exists else '<span class="evidence-warning">文件未确认存在</span>'
        cards.append(
            '<button class="shot-card" type="button" data-src="{url}" data-title="{title}">'
            '<img src="{url}" alt="{title}" loading="lazy">'
            '<span>{title}</span>{missing}'
            "</button>".format(url=esc(url), title=esc(name), missing=missing)
        )
    return f'<div class="shot-grid">{"".join(cards)}</div>'


def render_api_evidence(case: dict[str, Any]) -> str:
    requests = case.get("requests") or []
    responses = case.get("responses") or []
    if not requests and not responses:
        return '<div class="empty-state">未提供接口请求与响应证据</div>'
    return (
        '<details class="payload-box">'
        '<summary>查看接口请求与响应证据</summary>'
        '<div class="payload-grid">'
        f'<div><h4>请求证据</h4><pre>{esc(safe_json(requests))}</pre></div>'
        f'<div><h4>响应证据</h4><pre>{esc(safe_json(responses))}</pre></div>'
        '</div>'
        "</details>"
    )


def render_ui_detail(case: dict[str, Any]) -> str:
    return f"""
    <div class="detail-grid ui-detail">
      <section class="detail-panel">
        <h3>测试依据</h3>
        <p>{esc(case.get('basis') or '未提供')}</p>
        <h3>执行步骤</h3>
        {render_list(case.get('steps') or [], ordered=True)}
      </section>
      <section class="detail-panel">
        <h3>通过标准</h3>
        {render_list(case.get('pass_criteria') or [], ordered=True)}
        <h3>断言明细</h3>
        {render_assertions(case)}
      </section>
    </div>
    <section class="evidence-section">
      <h3>截图证据</h3>
      {render_screenshots(case)}
    </section>
"""


def render_api_detail(case: dict[str, Any]) -> str:
    note = case.get("note") or "按接口测试矩阵完成断言。"
    return f"""
    <div class="detail-grid api-detail">
      <section class="detail-panel">
        <h3>接口信息</h3>
        <dl class="meta-dl">
          <dt>接口</dt><dd>{esc(case.get('interface') or '未记录')}</dd>
          <dt>分类</dt><dd>{esc(case.get('category') or case.get('scope') or '未记录')}</dd>
          <dt>接口矩阵</dt><dd>{chip_group(case.get('matrix_ids') or [])}</dd>
          <dt>说明</dt><dd>{esc(note)}</dd>
        </dl>
      </section>
      <section class="detail-panel">
        <h3>断言明细</h3>
        {render_assertions(case)}
      </section>
    </div>
    <section class="evidence-section">
      <h3>接口证据</h3>
      {render_api_evidence(case)}
    </section>
"""


def render_ui_api_detail(case: dict[str, Any]) -> str:
    note = case.get("note") or "页面展示与接口返回按断言完成一致性核验。"
    return f"""
    <div class="detail-grid uiapi-detail">
      <section class="detail-panel">
        <h3>联动信息</h3>
        <dl class="meta-dl">
          <dt>联动范围</dt><dd>{esc(case.get('scope') or '未记录')}</dd>
          <dt>功能用例</dt><dd>{chip_group(case.get('related_cases') or [])}</dd>
          <dt>接口矩阵</dt><dd>{chip_group(case.get('matrix_ids') or [])}</dd>
          <dt>说明</dt><dd>{esc(note)}</dd>
        </dl>
      </section>
      <section class="detail-panel">
        <h3>断言明细</h3>
        {render_assertions(case)}
      </section>
    </div>
    <section class="evidence-section split-evidence">
      <div>
        <h3>截图证据</h3>
        {render_screenshots(case)}
      </div>
      <div>
        <h3>接口证据</h3>
        {render_api_evidence(case)}
      </div>
    </section>
"""


def render_case_detail(case: dict[str, Any]) -> str:
    if case["type"] == "API":
        return render_api_detail(case)
    if case["type"] == "UI+API":
        return render_ui_api_detail(case)
    return render_ui_detail(case)


def render_case(case: dict[str, Any]) -> str:
    status = case["status"]
    assertion_text = f'{case.get("assertion_passed", 0)}/{case.get("assertion_total", 0)} 条断言'
    screenshot_text = f'{len(case.get("screenshots") or [])} 张截图'
    reference_ids = case.get("related_cases") or case.get("matrix_ids") or []
    reference = render_chips(reference_ids, "关联依据")
    note = ""
    if case.get("blocked_reason"):
        note = f'<div class="case-note">阻塞原因：{esc(case["blocked_reason"])}</div>'
    elif case.get("note") and case["type"] == "UI":
        note = f'<div class="case-note">{esc(case["note"])}</div>'

    return f"""
<details class="case-card {esc(status)}" id="{esc(case['id'])}">
  <summary class="case-head">
    <span class="case-main">
      <span class="case-no">#{int(case.get('ordinal') or 0):03d}</span>
      <span class="case-id">{esc(case['id'])}</span>
      <span class="case-title">{esc(case['title'])}</span>
      <span class="case-type">{esc(case['type'])}</span>
    </span>
    <span class="case-side">
      <span class="pill {esc(status)}">{esc(case['status_label'])}</span>
      <span class="muted">{esc(assertion_text)}</span>
      <span class="muted">{esc(screenshot_text)}</span>
      <span class="expand-word" aria-hidden="true"></span>
    </span>
  </summary>
  <div class="case-body">
    <div class="case-relation">
      <div class="chip-line"><span class="chip-label">来源</span><span>{esc(case.get('suite_name') or '')}</span></div>
      {reference or '<div class="chip-line"><span class="chip-label">关联依据</span><span class="chip muted-chip">未提供</span></div>'}
    </div>
    {note}
    {render_case_detail(case)}
  </div>
</details>
"""


def render_suite_strip(suites: list[dict[str, Any]]) -> str:
    rows = []
    for suite in suites:
        loaded = "已读取" if suite.get("loaded") else "未读取"
        rows.append(
            '<div class="suite-item">'
            f'<strong>{esc(suite["suite_name"])}</strong>'
            f'<span>{esc(suite["suite_type"])} · {esc(loaded)} · {esc(suite.get("total", 0))} 个用例</span>'
            "</div>"
        )
    return f'<div class="suite-strip">{"".join(rows)}</div>'


def render_html(title: str, report_data: dict[str, Any]) -> str:
    summary = report_data["summary"]
    conclusion_label, conclusion_text = conclusion(summary)
    conclusion_class = "passed"
    if summary.get("failed", 0) > 0:
        conclusion_class = "failed"
    elif summary.get("blocked", 0) > 0:
        conclusion_class = "blocked"
    elif summary.get("warning", 0) > 0:
        conclusion_class = "warning"
    cases_html = "\n".join(render_case(case) for case in report_data["cases"])
    suites_html = render_suite_strip(report_data["suites"])
    stats = [
        ("总用例", summary["total"]),
        ("通过", summary["passed"]),
        ("失败", summary["failed"]),
        ("阻塞", summary["blocked"]),
        ("风险", summary["warning"]),
        ("断言通过", f'{summary["assertion_passed"]}/{summary["assertion_total"]}'),
        ("截图", summary["screenshot_total"]),
        ("通过率", f'{summary["pass_rate"]}%'),
    ]
    stat_cards = "".join(f'<div class="stat-card"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>' for label, value in stats)
    env_text = report_data.get("environment_text") or "未指定"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --panel: #ffffff;
      --panel-soft: #f8fafc;
      --text: #0f1f33;
      --muted: #64748b;
      --line: #d8e3f0;
      --brand: #1769e0;
      --green: #11845b;
      --green-bg: #e7f8ef;
      --red: #d92d20;
      --red-bg: #feeceb;
      --amber: #a15c07;
      --amber-bg: #fff4dc;
      --gray-bg: #eef2f7;
      --shadow: 0 12px 30px rgba(15, 31, 51, .08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
      line-height: 1.65;
      letter-spacing: 0;
    }}
    .page {{ width: min(1440px, calc(100vw - 48px)); margin: 28px auto 56px; }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 28px 30px;
    }}
    .hero-top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }}
    h1 {{ margin: 0; font-size: 28px; line-height: 1.3; }}
    .subtitle {{ margin: 8px 0 0; color: var(--muted); }}
    .conclusion {{
      min-width: 180px;
      text-align: right;
      font-weight: 700;
      color: var(--green);
    }}
    .conclusion strong {{ display: block; font-size: 26px; }}
    .conclusion.failed {{ color: var(--red); }}
    .conclusion.blocked, .conclusion.warning {{ color: var(--amber); }}
    .stats {{ display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }}
    .stat-card {{
      background: var(--panel-soft);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
      min-height: 78px;
    }}
    .stat-card span {{ display: block; color: var(--muted); font-size: 13px; }}
    .stat-card strong {{ display: block; margin-top: 6px; font-size: 24px; line-height: 1.2; }}
    .suite-strip {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .suite-item {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
    }}
    .suite-item strong {{ display: block; font-size: 14px; }}
    .suite-item span {{ display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }}
    .section {{
      margin-top: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 20px;
      border-bottom: 1px solid var(--line);
      background: #fbfdff;
    }}
    .section-head h2 {{ margin: 0; font-size: 22px; }}
    .section-head span {{ color: var(--muted); font-size: 13px; }}
    .case-list {{ padding: 16px; }}
    .case-card {{
      border: 1px solid var(--line);
      border-left-width: 5px;
      border-radius: 8px;
      background: var(--panel);
      margin-bottom: 12px;
      overflow: hidden;
    }}
    .case-card.passed {{ border-left-color: var(--green); }}
    .case-card.failed {{ border-left-color: var(--red); }}
    .case-card.blocked, .case-card.warning {{ border-left-color: #d97706; }}
    .case-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      cursor: pointer;
      list-style: none;
      padding: 17px 18px;
    }}
    .case-head::-webkit-details-marker {{ display: none; }}
    .case-main {{ display: flex; align-items: center; gap: 14px; min-width: 0; }}
    .case-no {{ color: #244d7d; font-weight: 800; white-space: nowrap; }}
    .case-id {{ color: #244d7d; font-weight: 700; white-space: nowrap; }}
    .case-title {{ font-weight: 700; font-size: 16px; overflow-wrap: anywhere; }}
    .case-type {{
      display: inline-flex;
      align-items: center;
      height: 24px;
      padding: 0 9px;
      border-radius: 999px;
      background: #eaf2ff;
      color: #195db8;
      font-size: 12px;
      white-space: nowrap;
    }}
    .case-side {{ display: flex; align-items: center; gap: 10px; white-space: nowrap; color: var(--muted); font-size: 13px; }}
    .expand-word {{ color: var(--brand); font-weight: 700; }}
    details[open] .expand-word {{ color: var(--muted); }}
    .expand-word::before {{ content: "展开"; }}
    details[open] .expand-word::before {{ content: "收起"; }}
    .case-body {{ border-top: 1px solid var(--line); background: #ffffff; }}
    .case-relation {{ display: flex; flex-wrap: wrap; gap: 8px 12px; padding: 12px 18px; border-bottom: 1px solid var(--line); background: #fbfdff; }}
    .chip-line {{ display: inline-flex; align-items: center; flex-wrap: wrap; gap: 6px; }}
    .chip-label {{ color: var(--muted); font-size: 12px; }}
    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 9px;
      border: 1px solid #b9d5f5;
      border-radius: 999px;
      background: #f2f8ff;
      color: #174f8f;
      font-size: 12px;
      font-weight: 700;
    }}
    .muted-chip {{ color: var(--muted); border-color: var(--line); background: var(--gray-bg); }}
    .case-meta, .case-note {{ margin: 0; padding: 12px 18px; border-bottom: 1px solid var(--line); color: var(--muted); }}
    .case-note {{ color: #8a4b08; background: var(--amber-bg); }}
    .detail-grid {{ display: grid; grid-template-columns: 320px minmax(0, 1fr); }}
    .detail-grid.api-detail {{ grid-template-columns: minmax(320px, 38%) minmax(0, 1fr); }}
    .detail-grid.uiapi-detail {{ grid-template-columns: minmax(320px, 38%) minmax(0, 1fr); }}
    .detail-panel {{ padding: 16px 18px; border-right: 1px solid var(--line); min-width: 0; }}
    .detail-panel:last-child {{ border-right: 0; }}
    .detail-panel h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .detail-panel h3:not(:first-child) {{ margin-top: 18px; }}
    .detail-panel p {{ margin: 0; color: #263a52; }}
    .meta-dl {{ display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: 10px 12px; margin: 0; }}
    .meta-dl dt {{ color: var(--muted); }}
    .meta-dl dd {{ margin: 0; min-width: 0; word-break: break-word; }}
    .evidence-section {{ padding: 14px 18px 18px; border-top: 1px solid var(--line); }}
    .evidence-section h3 {{ margin: 0 0 10px; font-size: 15px; }}
    .split-evidence {{ display: grid; grid-template-columns: minmax(280px, 40%) minmax(0, 1fr); gap: 16px; }}
    .text-list {{ margin: 0; padding-left: 20px; }}
    .text-list li {{ margin: 4px 0; }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 44px;
      min-height: 24px;
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }}
    .pill.passed {{ color: var(--green); background: var(--green-bg); }}
    .pill.failed {{ color: var(--red); background: var(--red-bg); }}
    .pill.blocked, .pill.warning {{ color: var(--amber); background: var(--amber-bg); }}
    .pill.skipped, .pill.unknown {{ color: var(--muted); background: var(--gray-bg); }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; word-break: break-word; }}
    th {{ background: #eaf2fa; font-size: 13px; }}
    td {{ font-size: 13px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .assertion-table th:nth-child(1) {{ width: 24%; }}
    .assertion-table th:nth-child(2), .assertion-table th:nth-child(3) {{ width: 32%; }}
    .assertion-table th:nth-child(4) {{ width: 90px; }}
    .shot-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }}
    .shot-card {{
      appearance: none;
      border: 1px solid var(--line);
      background: #ffffff;
      border-radius: 8px;
      padding: 8px;
      text-align: left;
      cursor: zoom-in;
      color: #174f8f;
      min-width: 0;
    }}
    .shot-card img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: contain;
      background: #f1f5f9;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
    }}
    .shot-card span {{ display: block; margin-top: 6px; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .evidence-warning {{ display: block; margin-top: 4px; color: var(--amber); font-size: 12px; }}
    .empty-state {{
      padding: 12px 14px;
      border: 1px dashed var(--line);
      border-radius: 8px;
      color: var(--muted);
      background: var(--panel-soft);
    }}
    .payload-box {{ margin-top: 10px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    .payload-box summary {{ cursor: pointer; padding: 10px 12px; color: var(--brand); font-weight: 700; background: #fbfdff; }}
    .payload-grid {{ display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid var(--line); }}
    .payload-grid > div:first-child {{ border-right: 1px solid var(--line); }}
    .payload-grid h4 {{ margin: 0; padding: 10px 12px; background: #f8fafc; border-bottom: 1px solid var(--line); font-size: 13px; }}
    pre {{
      margin: 0;
      padding: 14px;
      max-height: 420px;
      overflow: auto;
      background: #101828;
      color: #e6edf7;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .modal {{
      position: fixed;
      inset: 0;
      z-index: 50;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 32px;
      background: rgba(15, 23, 42, .72);
    }}
    .modal.active {{ display: flex; }}
    .modal-card {{
      width: min(1180px, 96vw);
      max-height: 92vh;
      background: #ffffff;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 24px 80px rgba(0, 0, 0, .32);
    }}
    .modal-head {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 16px; border-bottom: 1px solid var(--line); }}
    .modal-title {{ font-weight: 700; }}
    .modal-close {{ border: 1px solid var(--line); border-radius: 6px; background: #fff; padding: 6px 10px; cursor: pointer; }}
    .modal-card img {{ display: block; width: 100%; max-height: calc(92vh - 58px); object-fit: contain; background: #f8fafc; }}
    @media (max-width: 1100px) {{
      .stats {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .suite-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .detail-grid {{ grid-template-columns: 1fr; }}
      .detail-grid.api-detail, .detail-grid.uiapi-detail {{ grid-template-columns: 1fr; }}
      .detail-panel {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .detail-panel:last-child {{ border-bottom: 0; }}
      .split-evidence {{ grid-template-columns: 1fr; }}
      .payload-grid {{ grid-template-columns: 1fr; }}
      .payload-grid > div:first-child {{ border-right: 0; border-bottom: 1px solid var(--line); }}
    }}
    @media (max-width: 720px) {{
      .page {{ width: min(100vw - 24px, 680px); margin-top: 14px; }}
      .hero-top, .case-head {{ align-items: flex-start; flex-direction: column; }}
      .conclusion {{ text-align: left; min-width: 0; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .suite-strip {{ grid-template-columns: 1fr; }}
      .case-main {{ flex-wrap: wrap; }}
      .case-side {{ flex-wrap: wrap; white-space: normal; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1>{esc(title)}</h1>
          <p class="subtitle">环境：{esc(env_text)}　生成时间：{esc(report_data['generated_at'])}</p>
        </div>
        <div class="conclusion {esc(conclusion_class)}">
          <strong>{esc(conclusion_label)}</strong>
          <span>{esc(conclusion_text)}</span>
        </div>
      </div>
      <div class="stats">{stat_cards}</div>
      {suites_html}
    </section>

    <section class="section">
      <div class="section-head">
        <h2>用例执行明细</h2>
        <span>点击用例在当前页查看断言与证据</span>
      </div>
      <div class="case-list">
        {cases_html}
      </div>
    </section>
  </main>

  <div class="modal" id="image-modal" aria-hidden="true">
    <div class="modal-card">
      <div class="modal-head">
        <div class="modal-title" id="modal-title">截图预览</div>
        <button class="modal-close" type="button">关闭</button>
      </div>
      <img id="modal-image" alt="截图预览">
    </div>
  </div>

  <script>
    const modal = document.getElementById('image-modal');
    const modalImage = document.getElementById('modal-image');
    const modalTitle = document.getElementById('modal-title');
    document.querySelectorAll('[data-src]').forEach((button) => {{
      button.addEventListener('click', () => {{
        modalImage.src = button.dataset.src;
        modalTitle.textContent = button.dataset.title || '截图预览';
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
      }});
    }});
    function closeModal() {{
      modal.classList.remove('active');
      modal.setAttribute('aria-hidden', 'true');
      modalImage.removeAttribute('src');
    }}
    document.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {{
      if (event.target === modal) closeModal();
    }});
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape') closeModal();
    }});
  </script>
</body>
</html>
"""


def build_environment_text(args: argparse.Namespace, environment: dict[str, Any]) -> str:
    if args.active_environment:
        return args.active_environment
    if not environment:
        return "未指定"
    for key in ("active_environment", "environment", "env"):
        if environment.get(key):
            return str(environment[key])
    parts = []
    for key in ("ui_base_url", "api_base_url", "base_url"):
        if environment.get(key):
            parts.append(f"{key}={environment[key]}")
    return "；".join(parts) if parts else "未指定"


def self_check(output_dir: Path, report_data: dict[str, Any], html_text: str) -> dict[str, Any]:
    cases = report_data["cases"]
    summary = report_data["summary"]
    recomputed = build_summary(cases)
    checks = []

    def add(item: str, passed: bool, detail: str = "") -> None:
        checks.append({"item": item, "passed": bool(passed), "detail": detail})

    add("HTML 总报告存在", (output_dir / "index.html").exists())
    add("JSON 数据存在", (output_dir / "report-data.json").exists())
    stat_ok = all(summary.get(key) == recomputed.get(key) for key in ("total", "passed", "failed", "warning", "blocked", "skipped"))
    add("统计与明细一致", stat_ok, f"summary={summary}; recomputed={recomputed}")
    add("用例标题完整", all(case.get("title") and case.get("title") != "未命名用例" for case in cases))

    assertion_ok = True
    assertion_missing = []
    for case in cases:
        for assertion in case.get("assertions") or []:
            has_check = bool(assertion.get("check") or assertion.get("message") or assertion.get("name"))
            has_expected = "expected" in assertion
            has_actual = "actual" in assertion
            has_passed = "passed" in assertion
            if not (has_check and has_expected and has_actual and has_passed):
                assertion_ok = False
                assertion_missing.append(case.get("id"))
                break
    add("断言三元组完整", assertion_ok, ",".join(assertion_missing[:10]))

    screenshots = [shot for case in cases for shot in (case.get("screenshots") or [])]
    missing_shots = [shot.get("path") for shot in screenshots if not shot.get("exists")]
    add("截图证据可访问", not missing_shots, "；".join(missing_shots[:5]))
    add("报告正文不跳子报告", not any(word in html_text for word in FORBIDDEN_HTML_SECTIONS))
    add("截图使用弹窗预览", "id=\"image-modal\"" in html_text and "data-src=" in html_text)
    add("无 Unicode 转义", re.search(r"\\u[0-9a-fA-F]{4}", html_text) is None)
    add("未输出 Bearer Token", re.search(r"(?i)Bearer\s+(?!<已脱敏>)[A-Za-z0-9._~+/=-]{12,}", html_text) is None)
    add("未输出高敏字段明文", re.search(r"(?i)(token|cookie|password|secret|authorization|x-auth-token)[\"']?\s*[:=]\s*[\"'](?!<已脱敏>)[^\"']{8,}", html_text) is None)

    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def write_readme(output_dir: Path, title: str, summary: dict[str, Any]) -> None:
    text = f"""# {title}

本目录由 generate-automation-total-report 生成。

- `index.html`：单页自动化执行总报告
- `summary.json`：汇总统计
- `report-data.json`：结构化明细
- `report-self-check.json`：报告生成质量自检

统计：总用例 {summary['total']}，通过 {summary['passed']}，失败 {summary['failed']}，阻塞 {summary['blocked']}，风险 {summary['warning']}。
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    version = args.version
    output_dir = Path(args.output_dir).resolve() if args.output_dir else project_root / "automation" / "reports" / version / "automation-total" / "latest"
    output_dir.mkdir(parents=True, exist_ok=True)

    suites, cases, environment = load_suites(project_root, output_dir, version, args.suite)
    if not cases:
        raise SystemExit("未读取到任何自动化用例，请检查 suite 目录和 test-results.json。")

    summary = build_summary(cases)
    title = args.title or f"{version.upper()} 自动化执行总报告"
    report_data = {
        "schema_version": 1,
        "report_type": "automation_total",
        "version": version,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "environment": environment,
        "environment_text": build_environment_text(args, environment),
        "summary": summary,
        "suites": suites,
        "cases": cases,
    }

    html_text = render_html(title, report_data)
    (output_dir / "index.html").write_text(html_text, encoding="utf-8")
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "report-data.json", report_data)
    check_result = self_check(output_dir, report_data, html_text)
    write_json(output_dir / "report-self-check.json", check_result)
    write_readme(output_dir, title, summary)

    print(json.dumps({"output": str(output_dir), "summary": summary, "self_check_passed": check_result["passed"]}, ensure_ascii=False))
    if not check_result["passed"]:
        return 2
    if args.fail_on_test_failure and summary.get("failed", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
