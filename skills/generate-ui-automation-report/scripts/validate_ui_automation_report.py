from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import render_ui_automation_report as renderer


def read_bytes_no_bom(path: Path) -> bytes:
    return path.read_bytes()


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "passed" if passed else "failed", "detail": detail})


def validate_report(summary_path: Path, results_path: Path, html_path: Path | None, project_root: Path) -> dict[str, Any]:
    summary = renderer.read_json(summary_path)
    raw_cases = renderer.read_json(results_path)
    if not isinstance(raw_cases, list):
        raise SystemExit("test-results.json 顶层必须是数组")

    output_dir = html_path.parent if html_path else results_path.parent
    cases = renderer.normalize_cases(raw_cases, project_root, output_dir)
    checks = renderer.make_quality_checks(summary, cases)

    contract = renderer.read_json(renderer.CONTRACT_FILE)
    required_summary = contract["input"]["summary_required_fields"]
    missing_summary = [field for field in required_summary if field not in summary]
    add_check(checks, "摘要字段契约", not missing_summary, "缺失字段：" + "、".join(missing_summary) if missing_summary else "摘要字段完整")

    required_case = contract["input"]["case_required_fields"]
    missing_case_fields = []
    for case_index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            missing_case_fields.append(f"第 {case_index} 条不是对象")
            continue
        for field in required_case:
            if field not in raw_case:
                missing_case_fields.append(f"{raw_case.get('id', case_index)} 缺失 {field}")
    add_check(checks, "用例字段契约", not missing_case_fields, "；".join(missing_case_fields[:8]) if missing_case_fields else "用例字段完整")

    if html_path:
        html_exists = html_path.exists()
        add_check(checks, "HTML 文件存在", html_exists, str(html_path) if html_exists else "未找到 HTML 文件")
        if html_exists:
            html_bytes = read_bytes_no_bom(html_path)
            add_check(checks, "UTF-8 无 BOM", not html_bytes.startswith(b"\xef\xbb\xbf"), "未发现 BOM" if not html_bytes.startswith(b"\xef\xbb\xbf") else "HTML 带 BOM")
            html_text = html_bytes.decode("utf-8")
            html_checks = renderer.make_quality_checks(summary, cases, html_text)
            existing_names = {item["name"] for item in checks}
            for item in html_checks:
                if item["name"] not in existing_names:
                    checks.append(item)
            add_check(checks, "UI 自动化报告标识", 'data-report-type="ui-automation"' in html_text, "HTML 包含 UI 自动化报告标识" if 'data-report-type="ui-automation"' in html_text else "缺少 data-report-type")
            overview_pos = html_text.find('data-report-role="overview"')
            detail_pos = html_text.find('data-report-role="case-details"')
            add_check(checks, "首页先于用例明细", overview_pos >= 0 and detail_pos > overview_pos, "先展示总览，再展示用例明细" if overview_pos >= 0 and detail_pos > overview_pos else "报告顺序不符合总览优先")
            case_index_pos = html_text.find('data-report-role="case-index"')
            add_check(checks, "章节精简检查", case_index_pos < 0 and "用例覆盖概览" not in html_text, "HTML 未展示额外概览表" if case_index_pos < 0 and "用例覆盖概览" not in html_text else "HTML 仍展示额外概览表")
            large_image_pattern = r"<img[^>]+(?:width=\"(?:[8-9]\d{2,}|\d{4,})\"|height=\"(?:[5-9]\d{2,}|\d{4,})\")"
            add_check(checks, "无固定大图铺满", not re.search(large_image_pattern, html_text), "未发现固定大尺寸截图属性" if not re.search(large_image_pattern, html_text) else "存在固定大尺寸截图")

    failed = [item for item in checks if item["status"] != "passed"]
    return {
        "schema_version": 1,
        "generated_by": "generate-ui-automation-report",
        "summary": str(summary_path),
        "results": str(results_path),
        "html": str(html_path) if html_path else "",
        "counts": renderer.compute_counts(cases),
        "assertions": renderer.assertion_totals(cases),
        "screenshots": renderer.screenshot_totals(cases),
        "checks": checks,
        "result": "passed" if not failed else "failed",
        "failed_checks": failed
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 UI 自动化 HTML 报告质量")
    parser.add_argument("--summary", required=True, help="summary.json 路径")
    parser.add_argument("--results", required=True, help="test-results.json 路径")
    parser.add_argument("--html", help="HTML 报告路径")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    parser.add_argument("--output-json", help="输出自审 JSON")
    args = parser.parse_args()

    report = validate_report(
        Path(args.summary).resolve(),
        Path(args.results).resolve(),
        Path(args.html).resolve() if args.html else None,
        Path(args.project_root).resolve()
    )
    if args.output_json:
        Path(args.output_json).resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"validation_result: {report['result']}")
    print(f"cases: {report['counts']}")
    print(f"assertions: {report['assertions']}")
    print(f"screenshots: {report['screenshots']}")
    if report["failed_checks"]:
        print("failed_checks:")
        for item in report["failed_checks"]:
            print(f"- {item['name']}: {item['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
