#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
CONTRACT_FILE = SKILL_DIR / "assets" / "direct_report_contract.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def get_status(data: dict[str, Any]) -> str | None:
    conclusion = data.get("conclusion")
    if isinstance(conclusion, dict):
        value = conclusion.get("status") or conclusion.get("overall_status")
    else:
        value = conclusion
    if value is None:
        return None
    status = str(value).strip().split(":", 1)[0].split("：", 1)[0].upper()
    return status


def has_any(data: dict[str, Any], keys: list[str]) -> bool:
    return any(key in data and data[key] not in (None, "", []) for key in keys)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def field_difference_count(value: Any) -> int:
    if isinstance(value, dict):
        for key in ("count", "total", "rows", "mismatch_count"):
            if key in value:
                return int_or_zero(value.get(key))
        return len(as_list(value.get("samples")))
    if isinstance(value, list):
        return len(value)
    return int_or_zero(value)


def iter_field_difference_samples(value: Any) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    raw_items = as_list(value.get("samples") if isinstance(value, dict) else value)
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        nested = as_list(item.get("samples")) if "samples" in item else []
        if nested:
            samples.extend(sample for sample in nested if isinstance(sample, dict))
        else:
            samples.append(item)
    return samples


def has_readable_field_sample(sample: dict[str, Any]) -> bool:
    has_key = any(key in sample and sample.get(key) not in (None, "") for key in ("business_key", "key", "business_key_text", "source_id", "target_id"))
    has_source_value = any(key in sample for key in ("expected_value", "source_value", "expected"))
    has_target_value = any(key in sample for key in ("actual_value", "target_value", "actual"))
    return has_key and has_source_value and has_target_value


def business_keys_require_latest_locator(data: dict[str, Any]) -> bool:
    business_keys = data.get("business_keys")
    if not isinstance(business_keys, dict):
        return False
    key_text = json.dumps(business_keys.get("key") or business_keys, ensure_ascii=False, default=str)
    markers = ("ODS最新", "最新快照", "ods_batch_no", "doris_update_time", "doris_create_time")
    return any(marker in key_text for marker in markers)


def sample_has_latest_locator(sample: dict[str, Any]) -> bool:
    text = json.dumps(
        {
            "business_key": sample.get("business_key"),
            "business_key_text": sample.get("business_key_text"),
            "ods_latest_locator": sample.get("ods_latest_locator"),
            "target_id": sample.get("target_id"),
            "staging_id": sample.get("staging_id"),
            "staging_evidence": sample.get("staging_evidence"),
        },
        ensure_ascii=False,
        default=str,
    )
    markers = ("ODS最新", "最新快照", "date=", "ods_batch_no=", "doris_update_time=", "doris_create_time=")
    return any(marker in text for marker in markers)


def add_business_key_locator_errors(data: dict[str, Any], errors: list[str]) -> None:
    if not business_keys_require_latest_locator(data):
        return
    if field_difference_count(data.get("field_differences")) <= 0:
        return
    samples = iter_field_difference_samples(data.get("field_differences"))
    if samples and not any(sample_has_latest_locator(sample) for sample in samples):
        errors.append("快照类接口字段差异样例的业务键缺少 ODS 最新快照定位字段，不能只展示源对象 ID。")


def add_difference_sample_errors(data: dict[str, Any], errors: list[str]) -> None:
    field_differences = data.get("field_differences")
    if field_difference_count(field_differences) <= 0:
        return
    samples = iter_field_difference_samples(field_differences)
    if not samples:
        errors.append("字段差异数量大于 0，但缺少差异样例。")
        return
    if not any(has_readable_field_sample(sample) for sample in samples):
        errors.append("字段差异样例缺少业务键、预期值或实际值，不能定位差异。")


def add_blocked_evidence_errors(data: dict[str, Any], errors: list[str]) -> None:
    for index, item in enumerate(as_list(data.get("blocked_items")), start=1):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or item.get("result") or "BLOCKED").upper()
        if status != "BLOCKED":
            continue
        evidence = item.get("current_evidence") or item.get("evidence") or item.get("required_evidence")
        if evidence in (None, "", []):
            errors.append(f"第 {index} 个阻塞项缺少当前证据或所需证据说明。")


def validate_sections(html_text: str, sections: list[str], errors: list[str], label: str) -> None:
    for section in sections:
        if f"<h2>{section}</h2>" not in html_text:
            errors.append(f"{label} 缺少章节: {section}")


def add_raw_display_key_errors(html_text: str, errors: list[str]) -> None:
    raw_markers = [
        "各接口业务键见 items",
        "interface_name：",
        "interface_path：",
        "business_key：",
        "source_id：",
        "target_id：",
        "staging_id：",
        "staging_evidence：",
    ]
    hits = [marker for marker in raw_markers if marker in html_text]
    if hits:
        errors.append(f"主报告存在未中文化的内部结构字段: {'、'.join(hits)}")


def validate_input(args: argparse.Namespace) -> int:
    contract = load_json(args.contract or CONTRACT_FILE)
    data = load_json(args.input)
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        errors.append("输入 JSON 顶层必须是对象。")
    else:
        for key in contract["input"]["critical_keys"]:
            if key not in data or data[key] in (None, "", []):
                errors.append(f"缺少关键输入字段: {key}")
        if not has_any(data, contract["input"]["target_source_alternatives"]):
            errors.append("缺少目标来源字段: target_sources 或 target_source")
        if not has_any(data, contract["input"]["field_rule_alternatives"]):
            warnings.append("缺少字段规则基线: field_mapping_summary 或 field_assignment_rules；字段准确性不得直接判 PASS。")
        if "totals_summary" not in data:
            warnings.append("缺少 totals_summary；完整性不得直接判 PASS。")
        status = get_status(data)
        if status and status not in set(contract["statuses"]):
            errors.append(f"结论状态不合法: {status}")
        add_difference_sample_errors(data, errors)
        add_business_key_locator_errors(data, errors)
        add_blocked_evidence_errors(data, errors)
    print("Validation mode: input")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Input validation passed.")
    return 0


def validate_output(args: argparse.Namespace) -> int:
    contract = load_json(args.contract or CONTRACT_FILE)
    errors: list[str] = []
    warnings: list[str] = []
    html_path = Path(args.html)
    if not html_path.exists():
        errors.append(f"主 HTML 不存在: {html_path}")
    else:
        text = html_path.read_text(encoding="utf-8")
        if "<html" not in text.lower():
            errors.append("主报告不是 HTML 文档。")
        if "????" in text or "�" in text:
            errors.append("主报告存在乱码占位符或替换字符。")
        validate_sections(text, contract["output"]["main_sections"], errors, "主报告")
        if not args.allow_sensitive_terms:
            sensitive_value_patterns = [
                r"(?i)(password|passwd|secret|token|cookie|signature|private_key|access_key|app_secret)\s*[:=]\s*[^<\s]{6,}",
                r"(?i)AKIA[0-9A-Z]{16}",
            ]
            for pattern in sensitive_value_patterns:
                if re.search(pattern, text):
                    errors.append("主报告疑似包含敏感键值，请先脱敏。")
                    break
        if 'class="badge fail"' in text.lower():
            warnings.append("主报告包含 FAIL 状态，请确认结论和修复建议已说明影响范围。")
        add_raw_display_key_errors(text, errors)
    if args.detail_html:
        detail_path = Path(args.detail_html)
        if not detail_path.exists():
            errors.append(f"证据 HTML 不存在: {detail_path}")
        else:
            detail_text = detail_path.read_text(encoding="utf-8")
            validate_sections(detail_text, contract["output"]["detail_sections"], errors, "证据页")
            add_raw_display_key_errors(detail_text, errors)
    if args.json:
        data = load_json(Path(args.json))
        if not isinstance(data, dict):
            errors.append("JSON 明细顶层必须是对象。")
        else:
            status = get_status(data)
            if status and status not in set(contract["statuses"]):
                errors.append(f"JSON 明细结论状态不合法: {status}")
            add_difference_sample_errors(data, errors)
            add_business_key_locator_errors(data, errors)
            add_blocked_evidence_errors(data, errors)
    print("Validation mode: output")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Output validation passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验直连数据迁移报告输入/输出")
    subparsers = parser.add_subparsers(dest="command", required=True)
    input_parser = subparsers.add_parser("input")
    input_parser.add_argument("--input", required=True, type=Path)
    input_parser.add_argument("--contract", type=Path, default=None)
    input_parser.set_defaults(func=validate_input)
    output_parser = subparsers.add_parser("output")
    output_parser.add_argument("--html", required=True, type=Path)
    output_parser.add_argument("--json", type=Path, default=None)
    output_parser.add_argument("--detail-html", type=Path, default=None)
    output_parser.add_argument("--contract", type=Path, default=None)
    output_parser.add_argument("--allow-sensitive-terms", action="store_true")
    output_parser.set_defaults(func=validate_output)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
