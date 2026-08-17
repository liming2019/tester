from __future__ import annotations

import argparse
import json
import os
import re
from collections import OrderedDict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONTRACT_FILE = SKILL_DIR / "assets" / "report_contract.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def html_escape(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def normalize_status(status: Any) -> str:
    raw = str(status or "").strip().lower()
    if raw in {"passed", "pass", "success", "ok"}:
        return "passed"
    if raw in {"failed", "fail", "failure", "error"}:
        return "failed"
    if raw in {"blocked", "block"}:
        return "blocked"
    if raw in {"skipped", "skip", "ignored"}:
        return "skipped"
    return raw or "unknown"


def status_text(status: str) -> str:
    return {
        "passed": "通过",
        "failed": "失败",
        "blocked": "阻塞",
        "skipped": "跳过",
        "unknown": "未知"
    }.get(status, status)


def status_class(status: str) -> str:
    if status in {"passed", "failed", "blocked", "skipped"}:
        return status
    return "unknown"


def safe_anchor(value: Any) -> str:
    anchor = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "case").strip())
    return anchor.strip("-") or "case"


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def join_badges(values: list[Any], empty: str = "无", label: str = "") -> str:
    if not values:
        return f"<span class=\"muted\">{html_escape(empty)}</span>"
    prefix = f"{label}：" if label else ""
    return "".join(
        f"<span class=\"tag\" title=\"{html_escape(prefix)}{html_escape(item)}\">{html_escape(prefix)}{html_escape(item)}</span>"
        for item in values
    )


def resolve_asset(path_value: Any, project_root: Path, output_dir: Path) -> dict[str, Any]:
    raw = str(path_value or "").strip()
    if not raw:
        return {"raw": "", "abs": "", "href": "", "exists": False}
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / raw
    exists = candidate.exists()
    try:
        href = os.path.relpath(candidate, output_dir)
    except ValueError:
        href = str(candidate)
    href = href.replace("\\", "/")
    return {"raw": raw, "abs": str(candidate), "href": href, "exists": exists}


def normalize_assertion(assertion: dict[str, Any]) -> dict[str, Any]:
    check = assertion.get("check") or assertion.get("message") or assertion.get("name") or ""
    expected = assertion.get("expected") or ""
    actual = assertion.get("actual") or ""
    passed = assertion.get("passed")
    if isinstance(passed, str):
        passed = passed.strip().lower() in {"true", "passed", "pass", "1", "yes"}
    return {
        "check": check,
        "expected": expected,
        "actual": actual,
        "passed": bool(passed),
        "message": assertion.get("message") or check
    }


def normalize_cases(cases: list[dict[str, Any]], project_root: Path, output_dir: Path) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        assertions = [normalize_assertion(item) for item in as_list(case.get("assertions")) if isinstance(item, dict)]
        screenshots = []
        for shot in as_list(case.get("screenshots")):
            if not isinstance(shot, dict):
                continue
            resolved = resolve_asset(shot.get("path"), project_root, output_dir)
            screenshots.append({
                "name": shot.get("name") or Path(str(shot.get("path") or "")).name or "截图",
                "path": shot.get("path") or "",
                "href": resolved["href"],
                "abs": resolved["abs"],
                "exists": resolved["exists"]
            })
        status = normalize_status(case.get("status"))
        failed_assertions = [item for item in assertions if not item["passed"]]
        if failed_assertions and status == "passed":
            status = "failed"
        normalized.append({
            "index": index,
            "id": case.get("id") or f"UI-CASE-{index:03d}",
            "title": case.get("title") or case.get("测试标题") or "",
            "type": case.get("type") or "",
            "related_cases": as_list(case.get("related_cases")),
            "basis": case.get("basis") or "",
            "steps": as_list(case.get("steps")),
            "pass_criteria": as_list(case.get("pass_criteria")),
            "status": status,
            "assertions": assertions,
            "screenshots": screenshots,
            "failed_assertions": failed_assertions
        })
    return normalized


def compute_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(cases), "passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "unknown": 0}
    for case in cases:
        status = normalize_status(case.get("status"))
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1
    return counts


def assertion_totals(cases: list[dict[str, Any]]) -> dict[str, int]:
    total = sum(len(case["assertions"]) for case in cases)
    failed = sum(len(case["failed_assertions"]) for case in cases)
    return {"total": total, "passed": total - failed, "failed": failed}


def screenshot_totals(cases: list[dict[str, Any]]) -> dict[str, int]:
    total = sum(len(case["screenshots"]) for case in cases)
    missing = sum(1 for case in cases for shot in case["screenshots"] if not shot["exists"])
    return {"total": total, "missing": missing, "existing": total - missing}


def parse_markdown_matrix(path: Path | None) -> "OrderedDict[str, dict[str, str]]":
    rows: "OrderedDict[str, dict[str, str]]" = OrderedDict()
    if not path or not path.exists():
        return rows

    headers: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            headers = []
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        is_separator = all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)
        if is_separator:
            continue
        if "用例ID" in cells and "测试标题" in cells:
            headers = cells
            continue
        if not headers:
            continue
        padded = cells + [""] * max(0, len(headers) - len(cells))
        row = {headers[index]: padded[index] for index in range(len(headers))}
        case_id = (row.get("用例ID") or "").strip()
        if case_id:
            rows[case_id] = row
    return rows


def matrix_value(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def group_cases_by_related(cases: list[dict[str, Any]]) -> "OrderedDict[str, list[dict[str, Any]]]":
    groups: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for case in cases:
        related_cases = case.get("related_cases") or [case["id"]]
        for related_case in related_cases:
            key = str(related_case).strip() or case["id"]
            groups.setdefault(key, []).append(case)
    return groups


def aggregate_status(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "unknown"
    statuses = [normalize_status(case.get("status")) for case in cases]
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if all(status == "passed" for status in statuses):
        return "passed"
    if "skipped" in statuses:
        return "skipped"
    return "unknown"


def defect_groups_by_related(summary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for defect in as_list(summary.get("defect_groups")):
        if not isinstance(defect, dict):
            continue
        for related_case in as_list(defect.get("related_cases")):
            key = str(related_case).strip()
            if key:
                groups.setdefault(key, []).append(defect)
    return groups


MAPPING_KEY_TERMS = [
    "登录", "账号", "密码", "权限", "跳转", "上传", "识别", "同步", "失败", "字段", "回填", "项目版本",
    "对象类型", "报告生成时间", "执行数", "通过数", "失败数", "保存", "草稿", "提交", "预览", "来源",
    "详情", "抽屉", "附件", "下载", "列表", "筛选", "重置", "首页", "统计", "刷新", "正式", "阻塞",
    "异常", "未上传", "重复", "并发", "负责人", "结论", "兼容", "脱敏"
]


def case_search_text(case: dict[str, Any]) -> str:
    parts: list[str] = [
        str(case.get("title") or ""),
        str(case.get("basis") or "")
    ]
    parts.extend(str(item) for item in as_list(case.get("steps")))
    parts.extend(str(item) for item in as_list(case.get("pass_criteria")))
    for assertion in as_list(case.get("assertions")):
        if isinstance(assertion, dict):
            parts.extend([
                str(assertion.get("check") or ""),
                str(assertion.get("expected") or ""),
                str(assertion.get("actual") or "")
            ])
    return " ".join(parts)


def detect_mapping_warning(matrix_title: str, linked_cases: list[dict[str, Any]]) -> bool:
    title = str(matrix_title or "").strip()
    if not title or not linked_cases:
        return False
    corpus = " ".join(case_search_text(case) for case in linked_cases)
    if title in corpus:
        return False
    terms = [term for term in MAPPING_KEY_TERMS if term in title]
    if not terms:
        return False
    matched = sum(1 for term in terms if term in corpus)
    required = 1 if len(terms) == 1 else 2
    return matched < required


def build_execution_matrix(
    cases: list[dict[str, Any]],
    matrix_rows: "OrderedDict[str, dict[str, str]]",
    summary: dict[str, Any]
) -> list[dict[str, Any]]:
    grouped_cases = group_cases_by_related(cases)
    defects = defect_groups_by_related(summary)
    entries: list[dict[str, Any]] = []
    consumed: set[str] = set()

    for case_id, matrix_row in matrix_rows.items():
        linked_cases = grouped_cases.get(case_id, [])
        if not linked_cases:
            continue
        consumed.add(case_id)
        entries.append(build_execution_matrix_entry(case_id, matrix_row, linked_cases, defects.get(case_id, [])))

    for case_id, linked_cases in grouped_cases.items():
        if case_id in consumed:
            continue
        entries.append(build_execution_matrix_entry(case_id, {}, linked_cases, defects.get(case_id, [])))

    return entries


def build_execution_matrix_entry(
    case_id: str,
    matrix_row: dict[str, str],
    linked_cases: list[dict[str, Any]],
    defects: list[dict[str, Any]]
) -> dict[str, Any]:
    title = matrix_value(matrix_row, "测试标题", "用例标题", "用例主题")
    if not title:
        title = "；".join(case["title"] for case in linked_cases if case.get("title")) or "未提供"
    total_assertions = sum(len(case["assertions"]) for case in linked_cases)
    failed_assertions = sum(len(case["failed_assertions"]) for case in linked_cases)
    screenshot_count = sum(len(case["screenshots"]) for case in linked_cases)
    status = aggregate_status(linked_cases)
    mapping_warning = bool(matrix_row) and detect_mapping_warning(title, linked_cases)
    coverage = "映射待复核" if mapping_warning else "已执行" if linked_cases else "未执行"
    issue_note = "全部断言通过" if failed_assertions == 0 else "；".join(
        assertion["check"]
        for case in linked_cases
        for assertion in case["failed_assertions"]
    )
    if mapping_warning:
        issue_note = "自动化断言通过；关联自动化用例与矩阵测试标题不一致，需复核映射" if failed_assertions == 0 else f"{issue_note}；关联映射需复核"
    if not matrix_row:
        issue_note = f"{issue_note}；归类矩阵未找到该来源用例"

    return {
        "case_id": case_id,
        "title": title,
        "priority": matrix_value(matrix_row, "优先级", default="-"),
        "primary_method": matrix_value(matrix_row, "主验证方式", default="-"),
        "automation_advice": matrix_value(matrix_row, "自动化建议", default="-"),
        "script_owner": matrix_value(matrix_row, "脚本归属", default="-"),
        "evidence_requirement": matrix_value(matrix_row, "证据要求", default="-"),
        "suite": matrix_value(matrix_row, "执行套件", default="-"),
        "locator_scope": matrix_value(matrix_row, "是否纳入 UI 定位", default="-"),
        "locator_batch": matrix_value(matrix_row, "定位批次", default="-"),
        "pages": matrix_value(matrix_row, "定位页面", default="-"),
        "components": matrix_value(matrix_row, "定位组件", default="-"),
        "classification_note": matrix_value(matrix_row, "归类说明", default="未提供"),
        "status": status,
        "coverage": coverage,
        "linked_cases": linked_cases,
        "assertions_total": total_assertions,
        "assertions_passed": total_assertions - failed_assertions,
        "assertions_failed": failed_assertions,
        "screenshots_total": screenshot_count,
        "defects": defects,
        "mapping_warning": mapping_warning,
        "issue_note": issue_note
    }


def make_quality_checks(summary: dict[str, Any], cases: list[dict[str, Any]], html_text: str | None = None) -> list[dict[str, str]]:
    summary_counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
    actual_counts = compute_counts(cases)
    assertions = assertion_totals(cases)
    screenshots = screenshot_totals(cases)

    checks: list[dict[str, str]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "passed" if passed else "failed", "detail": detail})

    expected_counts = {key: int(summary_counts.get(key, 0) or 0) for key in ["total", "passed", "failed", "blocked"]}
    actual_core = {key: actual_counts.get(key, 0) for key in ["total", "passed", "failed", "blocked"]}
    add("执行统计一致", expected_counts == actual_core, f"摘要统计：{expected_counts}；明细统计：{actual_core}")

    empty_titles = [case["id"] for case in cases if not str(case.get("title") or "").strip()]
    add("测试标题完整", not empty_titles, "缺失标题用例：" + "、".join(empty_titles) if empty_titles else "全部用例标题非空")

    incomplete_assertions = []
    for case in cases:
        for index, assertion in enumerate(case["assertions"], start=1):
            if not assertion.get("check") or not assertion.get("expected") or not assertion.get("actual") or not isinstance(assertion.get("passed"), bool):
                incomplete_assertions.append(f"{case['id']}#{index}")
    add("断言三元组完整", not incomplete_assertions, "缺失断言字段：" + "、".join(incomplete_assertions) if incomplete_assertions else f"断言总数：{assertions['total']}")

    status_mismatch = []
    for case in cases:
        has_failed_assertion = bool(case["failed_assertions"])
        if case["status"] == "passed" and has_failed_assertion:
            status_mismatch.append(f"{case['id']} 标记通过但存在失败断言")
        if case["status"] == "failed" and not has_failed_assertion:
            status_mismatch.append(f"{case['id']} 标记失败但没有失败断言")
    add("用例结果与断言一致", not status_mismatch, "；".join(status_mismatch) if status_mismatch else "用例状态和断言结果一致")

    missing_shots = [f"{case['id']}:{shot['path']}" for case in cases for shot in case["screenshots"] if not shot["exists"]]
    add("截图证据可访问", not missing_shots, "缺失截图：" + "；".join(missing_shots[:5]) if missing_shots else f"截图总数：{screenshots['total']}")

    if html_text is not None:
        required_sections = ["overview", "metrics", "failure-impact", "case-details"]
        missing_sections = [role for role in required_sections if f'data-report-role="{role}"' not in html_text]
        add("固定章节完整", not missing_sections, "缺失章节：" + "、".join(missing_sections) if missing_sections else "固定章节完整")
        has_matrix_section = 'data-report-role="execution-matrix"' in html_text or "测试用例执行归类矩阵" in html_text
        add("不展示执行归类矩阵", not has_matrix_section, "HTML 正文未展示执行归类矩阵" if not has_matrix_section else "HTML 正文仍展示执行归类矩阵")
        has_case_index = 'data-report-role="case-index"' in html_text or "用例覆盖概览" in html_text
        add("章节精简检查", not has_case_index, "HTML 正文未展示额外概览表" if not has_case_index else "HTML 正文仍展示额外概览表")
        has_quality_section = 'data-report-role="quality-gates"' in html_text or "报告质量自审" in html_text or "报告产物校验" in html_text
        add("门禁不进入报告正文", not has_quality_section, "HTML 正文未展示生成器质量门禁" if not has_quality_section else "HTML 正文仍展示生成器质量门禁")

        add("截图缩略图展示", screenshots["total"] == 0 or "shot-thumb" in html_text, "截图使用缩略图入口" if "shot-thumb" in html_text else "当前无截图")
        has_modal = "id=\"shot-modal\"" in html_text and "data-shot-src=" in html_text and "shot-modal-image" in html_text
        add("截图弹窗预览", screenshots["total"] == 0 or has_modal, "点击截图在报告内弹窗预览" if has_modal else "截图未提供报告内弹窗预览")
        add("无 Unicode 转义", not re.search(r"\\u[0-9A-Fa-f]{4}", html_text), "HTML 中未发现 \\uXXXX" if not re.search(r"\\u[0-9A-Fa-f]{4}", html_text) else "HTML 中存在 \\uXXXX")

    sensitive_blob = json.dumps({"summary": summary, "cases": cases}, ensure_ascii=False)
    if html_text:
        sensitive_blob += "\n" + html_text
    sensitive_findings = scan_sensitive_text(sensitive_blob)
    add("敏感信息扫描", not sensitive_findings, "未发现 token/cookie/密码/密钥/连接串" if not sensitive_findings else "疑似敏感信息：" + "；".join(sensitive_findings[:5]))

    return checks


def scan_sensitive_text(text: str) -> list[str]:
    patterns = [
        ("Bearer token", r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
        ("Authorization header", r"(?i)authorization\s*[:=]\s*['\"]?[^'\"\s<]{12,}"),
        ("Cookie value", r"(?i)cookie\s*[:=]\s*['\"]?[^'\"<]{20,}"),
        ("Secret field", r"(?i)(token|password|passwd|pwd|secret|api_key|appsecret)\s*[:=]\s*['\"]?[^'\"\s<]{8,}"),
        ("Connection string", r"(?i)(jdbc|mysql|postgresql|mongodb|redis)://[^'\"<\s]+")
    ]
    findings = []
    for label, pattern in patterns:
        if re.search(pattern, text):
            findings.append(label)
    return findings


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return (
        "<div class=\"metric\">"
        f"<span>{html_escape(label)}</span>"
        f"<strong>{html_escape(value)}</strong>"
        f"<small>{html_escape(hint)}</small>"
        "</div>"
    )


def format_environment(environment: dict[str, Any]) -> str:
    if not environment:
        return "未提供"
    labels = {
        "active_environment": "环境",
        "login_strategy": "登录方式",
        "sensitive_data_policy": "敏感信息"
    }
    parts = []
    for key, value in environment.items():
        label = labels.get(str(key), str(key))
        if str(key) == "sensitive_data_policy":
            parts.append(f"{label}：已脱敏")
            continue
        text = str(value)
        if re.search(r"(?i)(token|cookie|password|passwd|pwd|secret|api_key|appsecret|authorization)", text):
            text = "已脱敏"
        parts.append(f"{label}：{text}")
    return "；".join(parts)


def render_defects(summary: dict[str, Any], cases: list[dict[str, Any]], project_root: Path, output_dir: Path) -> str:
    defect_groups = as_list(summary.get("defect_groups"))
    if not defect_groups:
        failed_cases = [case for case in cases if case["status"] == "failed"]
        defect_groups = [{
            "defect_id": "未归类",
            "title": "存在失败 UI 自动化用例",
            "related_cases": [item for case in failed_cases for item in case.get("related_cases", [])],
            "failed_case": case["id"],
            "failed_assertions": [assertion["check"] for case in failed_cases for assertion in case["failed_assertions"]],
            "evidence": [shot["path"] for case in failed_cases for shot in case["screenshots"]]
        } for case in failed_cases]

    if not defect_groups:
        return "<div class=\"empty-state\">当前执行范围内未发现失败用例。</div>"

    rows = []
    for defect in defect_groups:
        evidence_links = []
        for item in as_list(defect.get("evidence")):
            resolved = resolve_asset(item, project_root, output_dir)
            label = Path(str(item)).name or str(item)
            evidence_links.append(f"<a href=\"{html_escape(resolved['href'])}\" target=\"_blank\">{html_escape(label)}</a>")
        detail_rows = []
        for assertion in as_list(defect.get("failed_assertion_details")):
            if not isinstance(assertion, dict):
                continue
            detail_rows.append(
                "<li>"
                f"<b>{html_escape(assertion.get('check'))}</b>"
                f"<span>期望：{html_escape(assertion.get('expected'))}</span>"
                f"<span>实际：{html_escape(assertion.get('actual'))}</span>"
                "</li>"
            )
        if not detail_rows:
            detail_rows = [f"<li>{html_escape(item)}</li>" for item in as_list(defect.get("failed_assertions"))]
        rows.append(
            "<tr>"
            f"<td><b>{html_escape(defect.get('defect_id'))}</b><br><span class=\"muted\">{html_escape(defect.get('title'))}</span></td>"
            f"<td>{join_badges(as_list(defect.get('related_cases')))}</td>"
            f"<td><a href=\"#{safe_anchor(defect.get('failed_case'))}\">{html_escape(defect.get('failed_case'))}</a></td>"
            f"<td><ul class=\"compact-list\">{''.join(detail_rows)}</ul></td>"
            f"<td>{'<br>'.join(evidence_links) if evidence_links else '<span class=\"muted\">无</span>'}</td>"
            "</tr>"
        )
    return (
        "<table class=\"data-table\">"
        "<thead><tr><th>缺陷编号</th><th>关联用例</th><th>失败用例</th><th>失败断言与实际结果</th><th>证据</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_case_index(cases: list[dict[str, Any]]) -> str:
    rows = []
    for case in cases:
        total_assertions = len(case["assertions"])
        failed_assertions = len(case["failed_assertions"])
        result_note = "全部断言通过" if failed_assertions == 0 else "；".join(assertion["check"] for assertion in case["failed_assertions"])
        rows.append(
            "<tr>"
            f"<td><a href=\"#{safe_anchor(case['id'])}\">{html_escape(case['id'])}</a></td>"
            f"<td>{html_escape(case['title'])}</td>"
            f"<td><span class=\"badge {status_class(case['status'])}\">{status_text(case['status'])}</span></td>"
            f"<td>{join_badges(case['related_cases'])}</td>"
            f"<td>{total_assertions - failed_assertions}/{total_assertions}</td>"
            f"<td>{len(case['screenshots'])}</td>"
            f"<td>{html_escape(result_note)}</td>"
            "</tr>"
        )
    return (
        "<table class=\"data-table case-index-table\">"
        "<thead><tr><th>用例 ID</th><th>测试标题</th><th>结果</th><th>关联用例</th><th>断言通过</th><th>截图</th><th>结论说明</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_steps(title: str, values: list[Any]) -> str:
    if not values:
        return f"<h4>{html_escape(title)}</h4><p class=\"muted\">未提供</p>"
    items = "".join(f"<li>{html_escape(item)}</li>" for item in values)
    return f"<h4>{html_escape(title)}</h4><ol>{items}</ol>"


def render_assertions(case: dict[str, Any]) -> str:
    rows = []
    for assertion in case["assertions"]:
        result = "passed" if assertion["passed"] else "failed"
        rows.append(
            "<tr>"
            f"<td>{html_escape(assertion['check'])}</td>"
            f"<td>{html_escape(assertion['expected'])}</td>"
            f"<td>{html_escape(assertion['actual'])}</td>"
            f"<td><span class=\"badge {result}\">{'通过' if assertion['passed'] else '失败'}</span></td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"4\" class=\"muted\">未提供断言明细</td></tr>")
    return (
        "<table class=\"data-table assertion-table\">"
        "<thead><tr><th>检查项</th><th>期望</th><th>实际</th><th>结果</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_screenshots(case: dict[str, Any]) -> str:
    if not case["screenshots"]:
        return "<p class=\"muted\">未提供截图证据</p>"
    items = []
    for shot in case["screenshots"]:
        if shot["exists"]:
            items.append(
                "<button class=\"shot\" type=\"button\" data-shot-src=\"{href}\" data-shot-name=\"{name}\">"
                "<img class=\"shot-thumb\" src=\"{href}\" alt=\"{name}\">"
                "<span>{name}</span>"
                "</button>".format(href=html_escape(shot["href"]), name=html_escape(shot["name"]))
            )
        else:
            items.append(
                "<div class=\"shot missing-shot\">"
                f"<strong>{html_escape(shot['name'])}</strong>"
                f"<span>截图不存在：{html_escape(shot['path'])}</span>"
                "</div>"
            )
    return f"<div class=\"shot-grid\">{''.join(items)}</div>"


def render_case_details(cases: list[dict[str, Any]]) -> str:
    ordered = sorted(cases, key=lambda item: 0 if item["status"] == "failed" else 1)
    blocks = []
    for case in ordered:
        failed_count = len(case["failed_assertions"])
        total_assertions = len(case["assertions"])
        blocks.append(
            f"<details id=\"{safe_anchor(case['id'])}\" class=\"case-detail {status_class(case['status'])}\" data-case-status=\"{status_class(case['status'])}\">"
            "<summary>"
            "<span class=\"case-main\">"
            f"<b>{html_escape(case['id'])}</b>"
            f"<strong>{html_escape(case['title'])}</strong>"
            f"<span class=\"related-cases\">{join_badges(case['related_cases'], label='关联用例')}</span>"
            "</span>"
            "<span class=\"case-meta\">"
            f"<span class=\"badge {status_class(case['status'])}\">{status_text(case['status'])}</span>"
            f"<span>{total_assertions - failed_count}/{total_assertions} 条断言</span>"
            f"<span>{len(case['screenshots'])} 张截图</span>"
            "<span class=\"toggle-word\">展开</span>"
            "</span>"
            "</summary>"
            "<div class=\"case-body\">"
            "<div class=\"case-text\">"
            f"<h4>测试依据</h4><p>{html_escape(case['basis']) or '<span class=\"muted\">未提供</span>'}</p>"
            f"{render_steps('执行步骤', case['steps'])}"
            f"{render_steps('通过标准', case['pass_criteria'])}"
            "</div>"
            "<div class=\"case-evidence\">"
            "<h4>断言明细</h4>"
            f"{render_assertions(case)}"
            "<h4>截图证据</h4>"
            f"{render_screenshots(case)}"
            "</div>"
            "</div>"
            "</details>"
        )
    return "".join(blocks)


def render_key_values(items: list[tuple[str, Any]]) -> str:
    rows = []
    for label, value in items:
        display = html_escape(value) if str(value or "").strip() else '<span class="muted">未提供</span>'
        rows.append(
            "<tr>"
            f"<th>{html_escape(label)}</th>"
            f"<td>{display}</td>"
            "</tr>"
        )
    return f"<table class=\"kv-table\"><tbody>{''.join(rows)}</tbody></table>"


def render_defect_badges(defects: list[dict[str, Any]]) -> str:
    if not defects:
        return "<span class=\"muted\">无</span>"
    return "".join(
        f"<span class=\"tag defect-tag\" title=\"{html_escape(defect.get('title'))}\">{html_escape(defect.get('defect_id') or '未编号')}</span>"
        for defect in defects
    )


def render_automation_case(case: dict[str, Any]) -> str:
    failed_count = len(case["failed_assertions"])
    total_assertions = len(case["assertions"])
    return (
        f"<article id=\"{safe_anchor(case['id'])}\" class=\"auto-case {status_class(case['status'])}\">"
        "<header>"
        "<span>"
        f"<b>{html_escape(case['id'])}</b>"
        f"<strong>{html_escape(case['title'])}</strong>"
        "</span>"
        "<span class=\"auto-case-meta\">"
        f"<span class=\"badge {status_class(case['status'])}\">{status_text(case['status'])}</span>"
        f"<span>{total_assertions - failed_count}/{total_assertions} 条断言</span>"
        f"<span>{len(case['screenshots'])} 张截图</span>"
        "</span>"
        "</header>"
        "<div class=\"auto-case-body\">"
        "<div class=\"auto-case-text\">"
        f"<h4>测试依据</h4><p>{html_escape(case['basis']) or '<span class=\"muted\">未提供</span>'}</p>"
        f"{render_steps('执行步骤', case['steps'])}"
        f"{render_steps('通过标准', case['pass_criteria'])}"
        "</div>"
        "<div class=\"auto-case-evidence\">"
        "<h4>断言明细</h4>"
        f"{render_assertions(case)}"
        "<h4>截图证据</h4>"
        f"{render_screenshots(case)}"
        "</div>"
        "</div>"
        "</article>"
    )


def render_execution_matrix(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<div class=\"empty-state\">当前执行结果未关联到任何归类矩阵用例。</div>"

    rows = []
    for entry in entries:
        linked_cases = entry["linked_cases"]
        linked_case_ids = [case["id"] for case in linked_cases]
        assertion_ratio = f"{entry['assertions_passed']}/{entry['assertions_total']}"
        detail_cases = "".join(render_automation_case(case) for case in linked_cases)
        row_class = f"matrix-row {status_class(entry['status'])}"
        if entry.get("mapping_warning"):
            row_class += " mapping-warning"
        coverage_class = "coverage-warning" if entry.get("mapping_warning") else ""
        coverage_attr = f" class=\"{coverage_class}\"" if coverage_class else ""
        matrix_facts = render_key_values([
            ("优先级", entry["priority"]),
            ("主验证方式", entry["primary_method"]),
            ("自动化建议", entry["automation_advice"]),
            ("脚本归属", entry["script_owner"]),
            ("证据要求", entry["evidence_requirement"]),
            ("执行套件", entry["suite"]),
            ("是否纳入 UI 定位", entry["locator_scope"]),
            ("定位批次", entry["locator_batch"]),
            ("定位页面", entry["pages"]),
            ("定位组件", entry["components"]),
            ("归类说明", entry["classification_note"])
        ])
        rows.append(
            f"<details id=\"{safe_anchor(entry['case_id'])}\" class=\"{row_class}\" data-case-status=\"{status_class(entry['status'])}\">"
            "<summary class=\"matrix-summary\">"
            "<span class=\"matrix-cell matrix-source\">"
            f"<b>{html_escape(entry['case_id'])}</b>"
            f"<strong>{html_escape(entry['title'])}</strong>"
            f"<small>{html_escape(entry['priority'])} · {html_escape(entry['primary_method'])}</small>"
            "</span>"
            "<span class=\"matrix-cell\">"
            f"<span class=\"badge {status_class(entry['status'])}\">{status_text(entry['status'])}</span>"
            f"<small{coverage_attr}>{html_escape(entry['coverage'])}</small>"
            "</span>"
            f"<span class=\"matrix-cell matrix-tags\">{join_badges(linked_case_ids, empty='无')}</span>"
            f"<span class=\"matrix-cell\"><b>{html_escape(assertion_ratio)}</b><small>断言通过</small></span>"
            f"<span class=\"matrix-cell\"><b>{html_escape(entry['screenshots_total'])}</b><small>截图</small></span>"
            f"<span class=\"matrix-cell matrix-issue\">{html_escape(entry['issue_note'])}</span>"
            "<span class=\"matrix-cell matrix-toggle\">展开</span>"
            "</summary>"
            "<div class=\"matrix-detail\">"
            "<aside class=\"matrix-basis\">"
            "<h3>归类矩阵依据</h3>"
            f"{matrix_facts}"
            f"<h3>关联缺陷</h3><p>{render_defect_badges(entry['defects'])}</p>"
            "</aside>"
            "<div class=\"matrix-evidence\">"
            "<h3>自动化执行证据</h3>"
            f"{detail_cases}"
            "</div>"
            "</div>"
            "</details>"
        )

    return (
        "<div class=\"matrix-note\">本节按测试用例执行归类矩阵展示：一行对应一个原始测试用例，自动化用例、断言和截图在行内展开复核。</div>"
        "<div class=\"matrix-table-head\" aria-hidden=\"true\">"
        "<span>归类矩阵用例</span><span>结果</span><span>关联自动化用例</span><span>断言</span><span>截图</span><span>结论说明</span><span>操作</span>"
        "</div>"
        f"{''.join(rows)}"
    )


def base_css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f5f7fb;
  --panel: #ffffff;
  --text: #0f1f34;
  --muted: #5b6b82;
  --line: #d8e1ed;
  --head: #eaf1f8;
  --blue: #2468d8;
  --green: #0f8f5f;
  --red: #cc3333;
  --amber: #b87510;
  --shadow: 0 12px 28px rgba(31, 49, 77, .08);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.55;
}
a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }
.page { max-width: 1480px; margin: 0 auto; padding: 22px 24px 48px; }
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 6px solid var(--blue);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 20px 22px;
}
.hero h1 { margin: 0 0 8px; font-size: 24px; line-height: 1.25; }
.hero p { margin: 0; color: var(--muted); }
.hero-meta { display: grid; gap: 8px; min-width: 240px; color: var(--muted); }
.section {
  margin-top: 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.section > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
}
.section h2 { margin: 0; font-size: 18px; }
.section-body { padding: 16px 18px; }
.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}
.metric {
  min-height: 92px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fbfdff;
}
.metric span { display: block; color: var(--muted); }
.metric strong { display: block; margin-top: 8px; font-size: 28px; line-height: 1; }
.metric small { display: block; margin-top: 10px; color: var(--muted); }
.data-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.data-table th,
.data-table td {
  border: 1px solid var(--line);
  padding: 9px 10px;
  vertical-align: top;
  overflow-wrap: anywhere;
}
.data-table th {
  background: var(--head);
  text-align: left;
  font-weight: 700;
}
.matrix-note {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #d6e6f7;
  border-left: 4px solid var(--blue);
  border-radius: 8px;
  background: #f7fbff;
  color: var(--muted);
}
.matrix-table-head,
.matrix-summary {
  display: grid;
  grid-template-columns: minmax(260px, 1.2fr) 96px minmax(190px, .75fr) 86px 78px minmax(260px, 1fr) 64px;
  gap: 12px;
  align-items: center;
}
.matrix-table-head {
  display: none;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.matrix-table-head span,
.matrix-cell {
  min-width: 0;
  padding: 0;
  overflow-wrap: anywhere;
}
.matrix-row {
  margin-top: 12px;
  border: 1px solid var(--line);
  border-left: 5px solid var(--green);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: 0 8px 18px rgba(31, 49, 77, .06);
  overflow: hidden;
}
.matrix-row.mapping-warning { border-left-color: var(--amber); }
.matrix-row.failed { border-left-color: var(--red); }
.matrix-row summary {
  cursor: pointer;
  list-style: none;
  min-height: 86px;
  padding: 14px 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}
.matrix-row summary::-webkit-details-marker { display: none; }
.matrix-source {
  display: grid;
  gap: 4px;
}
.matrix-source b {
  color: #24486f;
  font-size: 13px;
}
.matrix-source strong {
  font-size: 16px;
  line-height: 1.35;
}
.matrix-source small,
.matrix-cell small {
  display: block;
  margin-top: 3px;
  color: var(--muted);
}
.matrix-tags {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 5px;
}
.matrix-tags .tag { margin: 0; }
.matrix-summary .matrix-cell:nth-child(4),
.matrix-summary .matrix-cell:nth-child(5) {
  min-height: 52px;
  display: grid;
  place-content: center;
  text-align: center;
  border: 1px solid #e0e8f2;
  border-radius: 8px;
  background: #f8fbff;
}
.matrix-summary .matrix-cell:nth-child(4) b,
.matrix-summary .matrix-cell:nth-child(5) b {
  font-size: 16px;
}
.matrix-issue {
  color: var(--muted);
  min-height: 46px;
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border: 1px dashed #d8e1ed;
  border-radius: 8px;
  background: #fbfdff;
  font-size: 13px;
}
.matrix-row.failed .matrix-issue {
  color: var(--red);
  font-weight: 700;
  border-color: #efb7b7;
  background: #fff6f6;
}
.matrix-row.mapping-warning:not(.failed) .matrix-issue,
.coverage-warning {
  color: var(--amber);
  font-weight: 700;
}
.matrix-row.mapping-warning:not(.failed) .matrix-issue {
  border-color: #edcf95;
  background: #fffaf0;
}
.matrix-toggle {
  color: var(--blue);
  font-weight: 700;
  text-align: center;
  min-height: 32px;
  display: inline-grid;
  place-items: center;
  border: 1px solid #c9daee;
  border-radius: 8px;
  background: #f3f8ff;
}
details[open] > summary .matrix-toggle { color: var(--muted); }
details[open] > summary .matrix-toggle::before { content: "收起"; font-size: 0; }
.matrix-detail {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  border-top: 1px solid var(--line);
  background: #ffffff;
}
.matrix-basis,
.matrix-evidence {
  padding: 14px 16px;
}
.matrix-basis {
  background: #fbfdff;
  border-right: 1px solid var(--line);
}
.matrix-basis h3,
.matrix-evidence h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.kv-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  margin-bottom: 14px;
}
.kv-table th,
.kv-table td {
  border: 1px solid var(--line);
  padding: 8px 9px;
  vertical-align: top;
  overflow-wrap: anywhere;
}
.kv-table th {
  width: 112px;
  background: var(--head);
  text-align: left;
}
.defect-tag {
  color: var(--red);
  background: #fae6e6;
  border-color: #f1b8b8;
}
.auto-case {
  margin-bottom: 12px;
  border: 1px solid var(--line);
  border-left: 4px solid var(--green);
  border-radius: 8px;
  overflow: hidden;
}
.auto-case.failed { border-left-color: var(--red); }
.auto-case header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #fbfdff;
  border-bottom: 1px solid var(--line);
}
.auto-case header span:first-child {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}
.auto-case header strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.auto-case-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  white-space: nowrap;
}
.auto-case-body {
  display: grid;
  grid-template-columns: 330px minmax(0, 1fr);
}
.auto-case-text,
.auto-case-evidence {
  padding: 12px;
}
.auto-case-text {
  border-right: 1px solid var(--line);
}
.auto-case-text h4,
.auto-case-evidence h4 {
  margin: 0 0 8px;
  font-size: 14px;
}
.auto-case-text p { margin: 0 0 12px; }
.auto-case-text ol { margin: 0 0 12px; padding-left: 20px; }
.badge, .tag {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.tag {
  margin: 0 5px 5px 0;
  color: #24486f;
  background: #eef5fc;
  border: 1px solid #c9daee;
}
.related-cases .tag {
  color: #1f4f86;
  background: #f3f8ff;
}
.badge.passed { color: var(--green); background: #e5f6ee; }
.badge.failed { color: var(--red); background: #fae6e6; }
.badge.blocked, .badge.skipped { color: var(--amber); background: #fff2d8; }
.badge.unknown { color: var(--muted); background: #eef1f5; }
.muted { color: var(--muted); }
.empty-state {
  border: 1px dashed var(--line);
  border-radius: 8px;
  padding: 18px;
  color: var(--muted);
  background: #fbfdff;
}
.compact-list { margin: 0; padding-left: 18px; }
.compact-list li { margin: 0 0 6px; }
.compact-list span { display: block; color: var(--muted); }
.case-detail {
  margin-top: 8px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 5px solid var(--green);
  border-radius: 8px;
  overflow: hidden;
}
.case-detail.failed { border-left-color: var(--red); }
.case-detail summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  min-height: 54px;
  padding: 10px 14px;
  cursor: pointer;
  list-style: none;
}
.case-detail summary::-webkit-details-marker { display: none; }
.case-main {
  display: grid;
  grid-template-columns: 140px minmax(180px, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-width: 0;
}
.case-main strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
}
.case-main b { color: #36506f; }
.case-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  color: var(--muted);
  white-space: nowrap;
}
.toggle-word { color: var(--blue); font-weight: 700; }
details[open] .toggle-word { color: var(--muted); }
details[open] .toggle-word::before { content: "收起"; font-size: 0; }
.case-body {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  border-top: 1px solid var(--line);
}
.case-text, .case-evidence { padding: 14px 16px; }
.case-text { border-right: 1px solid var(--line); background: #fbfdff; }
.case-text h4, .case-evidence h4 { margin: 0 0 8px; font-size: 14px; }
.case-text p { margin: 0 0 14px; }
.case-text ol { margin: 0 0 14px; padding-left: 20px; }
.assertion-table th:nth-child(4) { width: 86px; }
.shot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: 10px;
}
.shot {
  display: grid;
  grid-template-rows: 96px auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: #f8fbff;
  padding: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: zoom-in;
}
.shot:hover { border-color: #9abce8; box-shadow: 0 6px 16px rgba(36, 104, 216, .12); }
.shot-thumb {
  width: 100%;
  height: 96px;
  object-fit: contain;
  background: #eef3f9;
}
.shot span {
  padding: 7px 9px;
  color: #315173;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.missing-shot { padding: 10px; color: var(--red); }
.shot-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: none;
  place-items: center;
  padding: 28px;
  background: rgba(9, 21, 38, .66);
}
.shot-modal.open { display: grid; }
.shot-modal-panel {
  width: min(1180px, 96vw);
  max-height: 92vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 22px 60px rgba(0, 0, 0, .28);
}
.shot-modal-head,
.shot-modal-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
}
.shot-modal-foot { border-top: 1px solid var(--line); border-bottom: none; color: var(--muted); }
.shot-modal-title {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.shot-modal-close {
  min-width: 34px;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}
.shot-modal-body {
  min-height: 220px;
  overflow: auto;
  background: #eef3f9;
  display: grid;
  place-items: center;
  padding: 16px;
}
.shot-modal-body img {
  max-width: 100%;
  max-height: 76vh;
  object-fit: contain;
  background: #ffffff;
  border: 1px solid var(--line);
}
.footer-note { margin-top: 18px; color: var(--muted); font-size: 12px; }
@media (max-width: 980px) {
  .page { padding: 14px; }
  .hero, .case-body, .matrix-detail, .auto-case-body { grid-template-columns: 1fr; }
  .hero-meta { min-width: 0; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .case-text, .matrix-basis, .auto-case-text { border-right: none; border-bottom: 1px solid var(--line); }
  .case-detail summary, .case-main { grid-template-columns: 1fr; }
  .case-meta { justify-content: flex-start; flex-wrap: wrap; }
  .matrix-table-head { display: none; }
  .matrix-summary { grid-template-columns: 1fr; gap: 10px; }
  .matrix-cell { border-right: none; border-bottom: none; }
  .matrix-summary .matrix-cell:nth-child(4),
  .matrix-summary .matrix-cell:nth-child(5) {
    min-height: auto;
    place-content: start;
    text-align: left;
  }
  .matrix-toggle { width: fit-content; padding: 5px 12px; }
  .auto-case header { align-items: flex-start; flex-direction: column; }
  .auto-case-meta { flex-wrap: wrap; }
}
"""


def render_screenshot_modal() -> str:
    return """
<div class="shot-modal" id="shot-modal" aria-hidden="true">
  <div class="shot-modal-panel" role="dialog" aria-modal="true" aria-labelledby="shot-modal-title">
    <div class="shot-modal-head">
      <div class="shot-modal-title" id="shot-modal-title">截图预览</div>
      <button class="shot-modal-close" type="button" aria-label="关闭截图预览">×</button>
    </div>
    <div class="shot-modal-body">
      <img id="shot-modal-image" alt="截图预览">
    </div>
    <div class="shot-modal-foot">
      <span id="shot-modal-caption">截图证据</span>
      <a id="shot-modal-open-original" href="#" target="_blank" rel="noopener">打开原图</a>
    </div>
  </div>
</div>
<script>
(() => {
  const modal = document.getElementById('shot-modal');
  const image = document.getElementById('shot-modal-image');
  const title = document.getElementById('shot-modal-title');
  const caption = document.getElementById('shot-modal-caption');
  const original = document.getElementById('shot-modal-open-original');
  const closeButton = modal.querySelector('.shot-modal-close');
  const close = () => {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    image.removeAttribute('src');
  };
  document.querySelectorAll('.shot[data-shot-src]').forEach((button) => {
    button.addEventListener('click', () => {
      const src = button.getAttribute('data-shot-src');
      const name = button.getAttribute('data-shot-name') || '截图预览';
      image.src = src;
      image.alt = name;
      title.textContent = name;
      caption.textContent = name;
      original.href = src;
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
      closeButton.focus();
    });
  });
  closeButton.addEventListener('click', close);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) close();
  });
})();
</script>
"""


def render_html(
    summary: dict[str, Any],
    cases: list[dict[str, Any]],
    project_root: Path,
    output_path: Path,
    title: str,
    custom_css: str = ""
) -> str:
    output_dir = output_path.parent
    counts = compute_counts(cases)
    assertion_counts = assertion_totals(cases)
    screenshot_counts = screenshot_totals(cases)
    pass_rate = "0.0%"
    if counts["total"]:
        pass_rate = f"{counts['passed'] / counts['total'] * 100:.1f}%"

    result_status = "failed" if counts["failed"] else "blocked" if counts["blocked"] else "passed"
    conclusion = "不通过" if result_status == "failed" else "阻塞" if result_status == "blocked" else "通过"
    generated_at = summary.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    boundary = summary.get("report_boundary") or "未提供执行范围说明"
    environment = summary.get("environment") if isinstance(summary.get("environment"), dict) else {}
    env_text = format_environment(environment)
    recommendation = "存在失败用例，不建议把当前 V1.1 UI 自动化执行结果标记为通过。" if counts["failed"] else "当前 UI 自动化覆盖范围内未发现失败用例。"

    metrics = "".join([
        render_metric("用例总数", counts["total"], "执行明细记录"),
        render_metric("通过", counts["passed"], pass_rate),
        render_metric("失败", counts["failed"], "需要复核或提缺陷"),
        render_metric("阻塞", counts["blocked"], "未完成执行"),
        render_metric("断言", assertion_counts["total"], f"失败 {assertion_counts['failed']} 条"),
        render_metric("截图证据", screenshot_counts["total"], f"缺失 {screenshot_counts['missing']} 张")
    ])

    html_without_quality = (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html_escape(title)}</title>\n"
        f"<style>{base_css()}\n{custom_css}</style>\n"
        "</head>\n"
        "<body data-report-type=\"ui-automation\">\n"
        "<main class=\"page\">\n"
        "<section class=\"hero\" data-report-role=\"overview\">\n"
        "<div>\n"
        f"<h1>{html_escape(title)}</h1>\n"
        f"<p>{html_escape(boundary)}</p>\n"
        "</div>\n"
        "<div class=\"hero-meta\">\n"
        f"<span>报告结论：<span class=\"badge {result_status}\">{html_escape(conclusion)}</span></span>\n"
        f"<span>生成时间：{html_escape(generated_at)}</span>\n"
        f"<span>环境说明：{html_escape(env_text)}</span>\n"
        "</div>\n"
        "</section>\n"
        "<section class=\"section\" data-report-role=\"metrics\"><header><h2>执行结果汇总</h2><span class=\"muted\">总览优先，失败优先</span></header>"
        f"<div class=\"section-body\"><div class=\"metric-grid\">{metrics}</div></div></section>\n"
        "<section class=\"section\" data-report-role=\"failure-impact\"><header><h2>失败影响与缺陷聚合</h2>"
        f"<span class=\"muted\">{html_escape(recommendation)}</span></header>"
        f"<div class=\"section-body\">{render_defects(summary, cases, project_root, output_dir)}</div></section>\n"
        "<section class=\"section\" data-report-role=\"case-details\"><header><h2>用例执行明细</h2><span class=\"muted\">按需展开查看断言与证据</span></header>"
        f"<div class=\"section-body\">{render_case_details(cases)}</div></section>\n"
    )
    html = (
        html_without_quality
        + "<p class=\"footer-note\">本报告由 generate-ui-automation-report 生成；HTML 样式可替换，数据契约和外部自检不可省略。</p>\n"
        + "</main>\n"
        + render_screenshot_modal()
        + "</body>\n</html>\n"
    )
    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="生成中文 UI 自动化 HTML 测试报告")
    parser.add_argument("--summary", required=True, help="summary.json 路径")
    parser.add_argument("--results", required=True, help="test-results.json 路径")
    parser.add_argument("--output", required=True, help="输出 HTML 路径")
    parser.add_argument("--project-root", default=".", help="项目根目录，用于解析截图相对路径")
    parser.add_argument("--title", default="V1.1 UI 自动化测试报告", help="报告标题")
    parser.add_argument("--classification-matrix", help="可选测试用例执行归类矩阵 Markdown 路径")
    parser.add_argument("--css-file", help="可选自定义 CSS 文件")
    parser.add_argument("--write-normalized-json", help="可选输出归一化报告数据 JSON")
    args = parser.parse_args()

    summary_path = Path(args.summary).resolve()
    results_path = Path(args.results).resolve()
    output_path = Path(args.output).resolve()
    project_root = Path(args.project_root).resolve()
    summary = read_json(summary_path)
    raw_cases = read_json(results_path)
    if not isinstance(raw_cases, list):
        raise SystemExit("test-results.json 顶层必须是数组")

    custom_css = ""
    if args.css_file:
        custom_css = Path(args.css_file).read_text(encoding="utf-8-sig")

    cases = normalize_cases(raw_cases, project_root, output_path.parent)
    html = render_html(summary, cases, project_root, output_path, args.title, custom_css)
    write_text(output_path, html)

    if args.write_normalized_json:
        normalized = {
            "schema_version": 1,
            "generated_by": "generate-ui-automation-report",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": {
                "summary": str(summary_path),
                "results": str(results_path),
                "contract": str(CONTRACT_FILE)
            },
            "counts": compute_counts(cases),
            "assertions": assertion_totals(cases),
            "screenshots": screenshot_totals(cases),
            "quality_checks": make_quality_checks(summary, cases, html),
            "cases": cases
        }
        write_json(Path(args.write_normalized_json).resolve(), normalized)

    print(f"html_report: {output_path}")
    if args.write_normalized_json:
        print(f"normalized_json: {Path(args.write_normalized_json).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
