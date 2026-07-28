#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - runtime fallback
    sync_playwright = None


def default_contract_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "report_contract.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def load_contract(path: Path | None) -> dict[str, Any]:
    return load_json(path or default_contract_path())


def get_status(data: dict[str, Any]) -> str | None:
    conclusion = data.get("conclusion")
    if isinstance(conclusion, str):
        return conclusion
    if isinstance(conclusion, dict):
        for key in ("status", "result", "conclusion"):
            value = conclusion.get(key)
            if isinstance(value, str):
                return value
    return None


def get_identity(item: Any, keys: list[str]) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def infer_interface_names(data: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    keys = contract["interface_identity_keys"]
    names: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = get_identity(node, keys)
            if name:
                names.add(name)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for top_key in (
        "interface_inventory",
        "field_assignment_rules",
        "field_accuracy_summary",
        "field_accuracy_details",
        "field_differences",
        "relationship_differences",
        "file_differences",
    ):
        walk(data.get(top_key))

    return sorted(names)


def infer_chain_type(data: dict[str, Any], contract: dict[str, Any], requested: str = "auto") -> str:
    normalized = stringify(requested).lower()
    if normalized in {"direct", "staged"}:
        return normalized

    for key in contract.get("chain_type_keys", []):
        value = stringify(data.get(key)).lower()
        if value in {"direct", "staged"}:
            return value
        if value in {"source_to_target", "source-target", "直连", "源到目标"}:
            return "direct"
        if value in {"two_stage", "staged_chain", "分阶段", "两阶段"}:
            return "staged"

    staged_markers = (
        "staging_layer",
        "source_to_staging_summary",
        "staging_to_target_summary",
        "full_chain_consistency_summary",
    )
    if any(data.get(key) not in (None, "", [], {}) for key in staged_markers):
        return "staged"
    return "direct"


def has_any(data: dict[str, Any], keys: list[str]) -> bool:
    return any(data.get(key) not in (None, "", [], {}) for key in keys)


def collect_difference_samples(node: Any, required_keys: set[str]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if required_keys & node.keys():
            samples.append(node)
        for value in node.values():
            samples.extend(collect_difference_samples(value, required_keys))
    elif isinstance(node, list):
        for value in node:
            samples.extend(collect_difference_samples(value, required_keys))
    return samples


def validate_required_keys(
    label: str,
    items: list[Any],
    required_keys: list[str],
    errors: list[str],
) -> None:
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label} 第 {index} 项不是对象。")
            continue
        missing = [key for key in required_keys if key not in item]
        if missing:
            errors.append(f"{label} 第 {index} 项缺少字段: {', '.join(missing)}")


def validate_statuses(
    items: list[Any],
    label: str,
    status_key: str,
    allowed: set[str],
    errors: list[str],
) -> None:
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        value = item.get(status_key)
        if value is None:
            continue
        if value not in allowed:
            errors.append(f"{label} 第 {index} 项的 {status_key} 不合法: {value}")


def resolve_mode(
    requested_mode: str,
    interface_names: list[str],
    missing_critical: list[str],
    overall_status: str | None,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    if requested_mode == "draft":
        return "draft", notes

    if missing_critical:
        if requested_mode == "auto" and overall_status == "BLOCKED":
            notes.append("关键输入不完整，建议降级为 draft。")
            return "draft", notes

    if len(interface_names) > 1:
        if requested_mode == "standard":
            notes.append("识别到多个接口，已按约束升级为 full，输出主报告和分接口明细页。")
        return "full", notes
    if requested_mode == "full":
        notes.append("识别到单接口，已按约束降级为 standard，直接输出明细报告。")
    return "standard", notes


def validate_input(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    data = load_json(Path(args.input))
    errors: list[str] = []
    warnings: list[str] = []

    overall_status = get_status(data)
    chain_type = infer_chain_type(data, contract, args.chain_type)
    interface_names = infer_interface_names(data, contract)
    critical_keys = list(contract["input"]["common_critical_keys"])
    critical_keys.extend(contract["input"].get(f"{chain_type}_critical_keys", []))
    missing_critical = [key for key in critical_keys if data.get(key) in (None, "", [], {})]
    if not has_any(data, contract["input"].get("target_source_alternatives", [])):
        missing_critical.append("target_sources/target_source")
    mode, mode_notes = resolve_mode(args.mode, interface_names, missing_critical, overall_status)
    warnings.extend(mode_notes)

    if mode == "draft":
        if "conclusion" not in data:
            errors.append("draft 模式至少需要 conclusion。")
        if "blocked_items" not in data:
            warnings.append("draft 模式缺少 blocked_items，无法解释阻塞原因。")
    else:
        if missing_critical:
            errors.append(f"缺少关键输入字段: {', '.join(missing_critical)}")

    overall_allowed = set(contract["statuses"]["overall"])
    if overall_status and overall_status not in overall_allowed:
        errors.append(f"总体结论状态不合法: {overall_status}")

    source_inventory_items = as_list(data.get("source_field_inventory"))
    if mode != "draft" and not source_inventory_items:
        warnings.append("正式报告缺少 source_field_inventory，源字段盘点章节只能展示空态。")
    validate_required_keys(
        "source_field_inventory",
        source_inventory_items,
        contract["input"]["source_inventory_required_keys"],
        errors,
    )

    coverage_summary = data.get("field_rule_coverage_summary")
    if mode != "draft" and not isinstance(coverage_summary, dict):
        warnings.append("正式报告缺少 field_rule_coverage_summary，字段覆盖门禁只能依据明细字段判断。")
    elif isinstance(coverage_summary, dict):
        missing = [
            key
            for key in contract["input"]["coverage_summary_required_keys"]
            if key not in coverage_summary
        ]
        if missing:
            errors.append(f"field_rule_coverage_summary 缺少字段: {', '.join(missing)}")

    unmapped_items = as_list(data.get("unmapped_source_fields"))
    validate_required_keys(
        "unmapped_source_fields",
        unmapped_items,
        contract["input"]["unmapped_source_field_required_keys"],
        errors,
    )

    rule_items = as_list(data.get("field_assignment_rules"))
    validate_required_keys(
        "field_assignment_rules",
        rule_items,
        contract["input"]["field_rule_required_keys"],
        errors,
    )

    accuracy_items = as_list(data.get("field_accuracy_details")) or as_list(
        data.get("field_accuracy_summary")
    )
    validate_required_keys(
        "field_accuracy",
        accuracy_items,
        contract["input"]["field_accuracy_required_keys"],
        errors,
    )
    validate_statuses(
        accuracy_items,
        "field_accuracy",
        "status",
        set(contract["statuses"]["field"]),
        errors,
    )

    coverage_items = as_list(data.get("coverage_gaps"))
    validate_statuses(
        coverage_items,
        "coverage_gaps",
        "status",
        set(contract["statuses"]["coverage"]),
        errors,
    )

    sample_keys = set(contract["input"]["difference_sample_required_keys"])
    for group_name in contract["difference_groups"]:
        samples = collect_difference_samples(data.get(group_name), sample_keys)
        validate_required_keys(group_name, samples, list(sample_keys), errors)

    if overall_status == "PASS":
        if not (data.get("field_assignment_rules") or data.get("field_mapping_summary")):
            errors.append("PASS 结论缺少字段赋值规则: field_assignment_rules 或 field_mapping_summary")
        if not (data.get("field_accuracy_summary") or data.get("field_accuracy_details")):
            errors.append("PASS 结论缺少字段准确性核验结果: field_accuracy_summary 或 field_accuracy_details")

    if mode != "draft" and isinstance(coverage_summary, dict):
        unmapped_total = coverage_summary.get("unmapped_field_total", 0)
        gate_passed = coverage_summary.get("gate_passed")
        if unmapped_items or (isinstance(unmapped_total, int) and unmapped_total > 0) or gate_passed is False:
            errors.append("存在未纳入规则的源字段，禁止生成正式 HTML 报告。")

    print(f"Validation mode: input")
    print(f"Resolved chain type: {chain_type}")
    print(f"Resolved delivery mode: {mode}")
    if interface_names:
        print(f"Interfaces: {', '.join(interface_names)}")

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Input validation passed.")
    return 0


def validate_sections(
    html_text: str,
    sections: list[str],
    label: str,
    errors: list[str],
) -> None:
    for section in sections:
        marker = f">{section}<"
        if marker not in html_text and section not in html_text:
            errors.append(f"{label} 缺少章节: {section}")


def audit_html_layout(file_path: Path, viewport_width: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if sync_playwright is None:
        warnings.append("未检测到 Playwright，跳过版式自检。")
        return errors, warnings

    with sync_playwright() as playwright:
        browser = None
        launch_errors: list[str] = []
        for launch in (
            lambda: playwright.chromium.launch(channel="msedge", headless=True),
            lambda: playwright.chromium.launch(headless=True),
        ):
            try:
                browser = launch()
                break
            except Exception as exc:  # pragma: no cover - runtime fallback
                launch_errors.append(str(exc))
        if browser is None:
            warnings.append(
                "版式自检未能启动浏览器，已跳过。原因: "
                + " | ".join(launch_errors[:2])
            )
            return errors, warnings

        try:
            page = browser.new_page(viewport={"width": viewport_width, "height": 1200})
            page.goto(file_path.resolve().as_uri(), wait_until="networkidle")
            result = page.evaluate(
                """() => {
                    const doc = document.documentElement;
                    const body = document.body;
                    const pageOverflow = Math.max(doc.scrollWidth, body ? body.scrollWidth : 0) - doc.clientWidth;
                    const panels = [...document.querySelectorAll('.page, .panel, .hero, .toc')];
                    const offenders = panels
                        .map((element) => {
                            const rect = element.getBoundingClientRect();
                            return {
                                tag: element.tagName.toLowerCase(),
                                className: element.className,
                                rightOverflow: Number((rect.right - window.innerWidth).toFixed(2)),
                                leftOverflow: Number(Math.abs(Math.min(rect.left, 0)).toFixed(2)),
                            };
                        })
                        .filter((item) => item.rightOverflow > 2 || item.leftOverflow > 2);
                    const scrollWrappers = [...document.querySelectorAll('.table-wrap')]
                        .filter((element) => element.scrollWidth - element.clientWidth > 2)
                        .length;
                    return {
                        pageOverflow: Number(pageOverflow.toFixed(2)),
                        offenders,
                        scrollWrappers,
                    };
                }"""
            )
        finally:
            browser.close()

    if result["pageOverflow"] > 2:
        errors.append(f"{file_path.name} 存在页面级横向溢出，超出 {result['pageOverflow']}px。")
    if result["offenders"]:
        brief = "; ".join(
            f"{item['tag']}.{item['className']} 右溢出 {item['rightOverflow']}px"
            for item in result["offenders"][:3]
        )
        errors.append(f"{file_path.name} 存在容器级横向溢出: {brief}")
    if result["scrollWrappers"]:
        warnings.append(f"{file_path.name} 有 {result['scrollWrappers']} 个表格使用横向滚动作为兜底。")
    return errors, warnings


def validate_output(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    data = load_json(Path(args.json))
    errors: list[str] = []
    warnings: list[str] = []

    meta = data.get("_report_meta") if isinstance(data.get("_report_meta"), dict) else {}
    requested_chain_type = args.chain_type if args.chain_type != "auto" else stringify(meta.get("chain_type") or "auto")
    chain_type = infer_chain_type(data, contract, requested_chain_type)
    interface_names = infer_interface_names(data, contract)
    mode, mode_notes = resolve_mode(args.mode, interface_names, [], get_status(data))
    warnings.extend(mode_notes)
    mode_policy = contract["delivery_modes"][mode]
    interface_sections = contract["output"]["interface_sections_by_chain"][chain_type]

    if mode != "draft":
        if not args.html:
            errors.append("正式 HTML 模式必须提供 HTML 路径。")
        else:
            html_path = Path(args.html)
            if not html_path.exists():
                errors.append(f"HTML 不存在: {html_path}")
            else:
                html_text = html_path.read_text(encoding="utf-8")
                if "<html" not in html_text.lower():
                    errors.append("输出文件不是 HTML 文档。")
                if "????" in html_text:
                    errors.append("输出文件存在乱码占位符 '????'。")
                if mode_policy["requires_main_html"]:
                    validate_sections(html_text, contract["output"]["main_sections_multi"], "主报告", errors)
                else:
                    validate_sections(html_text, interface_sections, "单接口明细报告", errors)
                if mode_policy["requires_main_html"] and mode_policy["requires_interface_pages"] and ".html" not in html_text:
                    errors.append("主报告缺少分接口 HTML 跳转链接。")
                if not args.skip_layout_check:
                    layout_errors, layout_warnings = audit_html_layout(html_path, args.viewport_width)
                    errors.extend(layout_errors)
                    warnings.extend(layout_warnings)

    if mode_policy["requires_interface_pages"]:
        if not args.interface_dir:
            errors.append(f"{mode} 模式必须提供分接口 HTML 目录。")
        else:
            interface_dir = Path(args.interface_dir)
            if not interface_dir.exists():
                errors.append(f"分接口目录不存在: {interface_dir}")
            else:
                html_files = sorted(interface_dir.glob("*.html"))
                expected_count = max(len(interface_names), 1)
                if len(html_files) < expected_count:
                    errors.append("分接口 HTML 数量少于识别到的接口数量。")
                for file_path in html_files:
                    text = file_path.read_text(encoding="utf-8")
                    validate_sections(
                        text,
                        interface_sections,
                        f"分接口页 {file_path.name}",
                        errors,
                    )
                    if not args.skip_layout_check:
                        layout_errors, layout_warnings = audit_html_layout(file_path, args.viewport_width)
                        errors.extend(layout_errors)
                        warnings.extend(layout_warnings)

    print(f"Validation mode: output")
    print(f"Resolved chain type: {chain_type}")
    print(f"Resolved delivery mode: {mode}")

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Output validation passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 API 迁移核验报告输入和输出。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    input_parser = subparsers.add_parser("input", help="校验结构化输入")
    input_parser.add_argument("--input", required=True, help="结构化输入 JSON 路径")
    input_parser.add_argument(
        "--mode",
        choices=("auto", "draft", "standard", "full"),
        default="auto",
        help="期望交付模式",
    )
    input_parser.add_argument(
        "--chain-type",
        choices=("auto", "direct", "staged"),
        default="auto",
        help="迁移链路类型；auto 会按输入字段推断",
    )
    input_parser.add_argument("--contract", type=Path, default=None, help="contract JSON 路径")
    input_parser.set_defaults(func=validate_input)

    output_parser = subparsers.add_parser("output", help="校验生成后的交付物")
    output_parser.add_argument("--json", required=True, help="结构化 JSON 路径")
    output_parser.add_argument("--html", help="主报告或单接口明细 HTML 路径")
    output_parser.add_argument("--interface-dir", help="分接口 HTML 目录")
    output_parser.add_argument(
        "--mode",
        choices=("auto", "draft", "standard", "full"),
        default="auto",
        help="期望交付模式",
    )
    output_parser.add_argument(
        "--chain-type",
        choices=("auto", "direct", "staged"),
        default="auto",
        help="迁移链路类型；auto 会按 JSON 元信息或输入字段推断",
    )
    output_parser.add_argument(
        "--viewport-width",
        type=int,
        default=1366,
        help="版式自检使用的浏览器宽度",
    )
    output_parser.add_argument(
        "--skip-layout-check",
        action="store_true",
        help="跳过 Playwright 版式自检",
    )
    output_parser.add_argument("--contract", type=Path, default=None, help="contract JSON 路径")
    output_parser.set_defaults(func=validate_output)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
