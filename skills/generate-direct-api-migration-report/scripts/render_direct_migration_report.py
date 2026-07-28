#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_FILE = SKILL_DIR / "assets" / "direct_report_template.html"
CONTRACT_FILE = SKILL_DIR / "assets" / "direct_report_contract.json"
SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|cookie|signature|private_key|access_key|app_secret)",
    re.IGNORECASE,
)
SENSITIVE_EXACT_KEYS = {
    "access_token",
    "refresh_token",
    "encrypt_token",
    "token",
    "cookie",
    "password",
    "passwd",
    "signature",
    "private_key",
    "access_key",
    "app_secret",
}
SAFE_TOKEN_STAT_RE = re.compile(r"(count|rows|shops|total|scope|summary|credential|target|top|unverified|expired)", re.IGNORECASE)

KEY_LABELS = {
    "migration_type": "迁移类型",
    "api_name": "接口名称",
    "api_path": "接口路径",
    "doc_url": "接口文档地址",
    "input_file": "输入文档",
    "platform": "平台",
    "date_range": "日期范围",
    "shop_scope": "店铺范围",
    "target_table": "目标表",
    "verification_time_basis": "核验时间基准",
    "source_business_date_min": "源业务日期最小值",
    "source_business_date_max": "源业务日期最大值",
    "bill_time_min": "动账时间最小值",
    "bill_time_max": "动账时间最大值",
    "target_create_time_min": "目标创建时间最小值",
    "target_create_time_max": "目标创建时间最大值",
    "target_update_time_min": "目标更新时间最小值",
    "target_update_time_max": "目标更新时间最大值",
    "source_type": "源类型",
    "source_interface": "源接口",
    "source_doc": "源接口文档",
    "source_request_scope": "源请求范围",
    "authorized_shop_count": "授权店铺数",
    "live_executable_credential_shop_count": "可实时调用凭据店铺数",
    "source_record_count": "源记录数",
    "source_field_inventory": "源字段清单",
    "source_fields_not_persisted": "源接口提供但未入库字段",
    "source_field": "源接口字段",
    "source_field_name": "源接口字段",
    "source_field_path": "源接口字段路径",
    "source_field_origin": "源接口字段来源",
    "source_id": "源记录标识",
    "target_id": "目标记录标识",
    "staging_id": "中间证据标识",
    "staging_evidence": "中间证据",
    "actual_value": "实际值",
    "actual_source_field_total": "实际源字段总数",
    "actual_source_fields": "实际源字段",
    "body_fetch_status": "文档正文抓取状态",
    "documented_expected_field_total": "官方文档字段总数",
    "documented_expected_fields": "官方文档字段",
    "documented_response_field_count": "文档响应字段数",
    "documented_response_fields": "文档响应字段",
    "field_contract_gate_status": "字段合同门禁状态",
    "field_contract_source": "字段合同来源",
    "legacy_fallback_fields": "历史兜底字段",
    "live_actual_fields": "实时样本字段",
    "live_extra_field_total": "实时额外字段数",
    "live_extra_fields": "实时额外字段",
    "sample_uncovered_documented_field_total": "样本未覆盖文档字段数",
    "sample_uncovered_documented_fields": "样本未覆盖文档字段",
    "schema_fetch_status": "内部 schema 抓取状态",
    "schema_missing_fields": "schema 缺少文档字段",
    "schema_only_field_total": "schema 独有字段数",
    "schema_only_fields": "schema 独有字段",
    "schema_reference_field_count": "schema 参考字段数",
    "schema_reference_fields": "schema 参考字段",
    "target_field_declarations": "目标字段声明数",
    "target_field_declaration_count": "目标字段声明数",
    "accuracy_matrix_fields": "准确性核验字段数",
    "accuracy_matrix_scope": "准确性核验范围",
    "source_mapped_fields": "源接口映射字段数",
    "system_generated_fields": "系统生成字段数",
    "migration_technical_fields": "迁移技术字段数",
    "target_trace_fields": "目标追踪字段数",
    "source_fields_not_persisted_status": "接口字段未入库核验状态",
    "source_fields_not_persisted_count": "接口字段未入库数量",
    "target_field": "目标字段",
    "target_field_match": "目标字段匹配",
    "field_role": "字段角色",
    "required_evidence": "所需证据",
    "source_scope_filter": "源范围过滤条件",
    "precheck": "前置检查",
    "app_key_present": "AppKey 是否配置",
    "app_secret_present": "AppSecret 是否配置",
    "target_type": "目标类型",
    "target_database": "目标数据库",
    "target_rows": "目标记录数",
    "target_shops_with_data": "目标有数据店铺数",
    "target_distinct_business_keys": "目标去重业务键数",
    "target_latest_dedup_rows": "目标按最新行去重记录数",
    "target_latest_dedup_record_count": "目标按最新行去重记录数",
    "target_latest_rule": "目标最新行规则",
    "target_latest_selection_rule": "目标重复取最新规则",
    "target_latest_sort_value": "目标最新行排序值",
    "target_duplicate_match_rule": "目标重复匹配规则",
    "target_batch_count": "目标批次数",
    "target_date_distribution": "目标日期分布",
    "auxiliary_cross_reference": "辅助交叉参考",
    "dwd_table": "DWD 表",
    "dwd_rows": "DWD 记录数",
    "ods_dwd_key_diff": "ODS 与 DWD 业务键差异",
    "side": "差异方向",
    "missing_keys": "缺失业务键数",
    "strict_value_observations": "严格值差异观察",
    "note": "说明",
    "key": "业务键",
    "items": "明细项",
    "business_key": "业务键",
    "business_key_text": "业务键",
    "key_type": "业务键类型",
    "target_distinct_keys": "目标去重键数",
    "target_duplicate_business_keys": "目标重复业务键数",
    "target_duplicate_extra_rows": "目标重复额外行数",
    "unique_status": "唯一性状态",
    "ambiguity": "歧义说明",
    "source_rows": "源记录数",
    "target_count": "目标数量",
    "missing_count": "缺失数量",
    "extra_count": "额外数量",
    "field_difference_count": "字段差异数量",
    "field_count": "差异字段数",
    "database_side_out_of_scope_rows": "数据库侧超范围记录数",
    "database_side_quality_rows": "数据库侧质量检查记录数",
    "duplicate_count": "重复数量",
    "target_duplicate_count": "目标重复数量",
    "max_duplicate_count": "最大重复次数",
    "status": "状态",
    "count": "数量",
    "total": "总数",
    "rows": "记录数",
    "rows_total": "记录数",
    "date": "日期",
    "shops_with_data": "有数据店铺数",
    "shops_with_target_data": "目标有数据店铺数",
    "distinct_business_keys": "去重业务键数",
    "reason": "原因",
    "blocked_item": "阻塞项编号",
    "impact": "影响",
    "gap_item": "覆盖缺口",
    "current_evidence": "当前证据",
    "impact_scope": "影响范围",
    "summary": "汇总",
    "total_dd_rows": "DD 总记录数",
    "authorized_rows": "已授权记录数",
    "authorized_unexpired_rows": "授权未过期记录数",
    "authorized_null_expire_rows": "授权到期时间为空记录数",
    "min_expire_at": "最早到期时间",
    "max_expire_at": "最晚到期时间",
    "source_scope_match": "源范围匹配",
    "source_scope_matched_shops": "源范围匹配店铺数",
    "source_scope_authorized_rows": "源范围已授权记录数",
    "source_scope_authorized_unexpired_rows": "源范围授权未过期记录数",
    "downstream_observation_not_ods_failure": "下游观察不计入 ODS 失败",
    "product_name": "商品名称（product_name）",
    "author_name": "达人名称（author_name）",
    "free_commission_flag": "是否免佣（free_commission_flag）",
    "collection_subject_name": "商户主体名称（collection_subject_name）",
    "priority": "优先级",
    "action": "建议动作",
    "recommendation": "建议",
    "expected_benefit": "预期收益",
    "expected_value": "预期值",
    "benefit": "收益",
    "sign_doc": "签名文档地址",
    "source_distinct_business_keys": "源去重业务键数",
    "source_distinct_keys": "源去重键数",
    "common_key_count": "源目标共同业务键数",
    "source_duplicate_business_keys": "源重复业务键数",
    "source_duplicate_extra_rows": "源重复额外行数",
    "auth_scope_target_rows": "授权范围目标记录数",
    "authorization_scope_summary": "授权范围汇总",
    "auth_token_unexpired_shops": "auth_token 未过期且有 token 店铺数",
    "shop_authorization_unexpired_shops": "shop_authorization 授权未过期店铺数",
    "intersection_auth_scope_shops": "双表授权交集店铺数",
    "live_token_in_intersection_shops": "交集内 token 可调用店铺数",
    "auth_token_only_unexpired_shops": "仅 auth_token 未过期店铺数",
    "shop_authorization_only_unexpired_shops": "仅 shop_authorization 未过期店铺数",
    "source_request_pages": "源请求页数",
    "interface_name": "接口名称",
    "interface_path": "接口路径",
    "source_presence_probe_pages": "源存在性探测页数",
    "source_request_elapsed_ms": "源请求耗时(ms)",
    "request_parameter_summary": "请求参数摘要",
    "method": "请求方法",
    "path": "请求路径",
    "date_granularity": "日期粒度",
    "page_size": "单页条数",
    "pagination": "分页规则",
    "no_target_shop_probe": "无目标店铺探测",
    "time_type": "时间类型",
    "signed_fields": "参与签名字段",
    "excluded_from_sign": "不参与签名字段",
    "param_json_serialization": "参数 JSON 序列化",
    "request_samples": "请求样例",
    "request_id": "请求ID",
    "http_status": "HTTP状态",
    "message": "响应信息",
    "code": "响应码",
    "successful_source_pages": "源请求成功页数",
    "failed_source_pages": "源请求失败页数",
    "sample_shop_count": "样本店铺数",
    "sample_shop_hashes": "样本店铺哈希",
    "sample_shop_target_rows": "样本店铺目标记录数",
    "sample_fetch_elapsed_seconds": "样本拉取耗时(秒)",
    "full_scope_attempts": "全范围拉取尝试",
    "live_token_target_rows": "可调用凭据目标记录数",
    "token_expired_target_rows": "短期令牌过期目标记录数",
    "out_of_current_auth_scope_rows": "当前授权范围外目标记录数",
    "target_quality": "目标质量检查",
    "live_token_top_target_shops": "可调用凭据目标店铺样例",
    "token_expired_top_target_shops": "令牌过期目标店铺样例",
    "sample_target_rows": "样本目标记录数",
    "unverified_live_token_target_rows": "未覆盖可调用凭据目标记录数",
    "unverified_auth_scope_target_rows": "未覆盖授权范围目标记录数",
    "attempt": "尝试任务",
    "result": "结果",
    "mismatch_count": "不匹配数量",
    "timeout_seconds": "超时时间(秒)",
    "row_count": "记录数",
    "shop_hash": "店铺哈希",
    "failed_fields": "失败字段",
    "sample_rows": "样本记录数",
    "sample_shop_hash": "样本店铺哈希",
    "sample_source_rows": "样本源记录数",
    "sample_missing": "样本缺失数",
    "sample_extra": "样本额外数",
    "sample_field_diff": "样本字段差异数",
    "token_expired_shops_in_auth_scope": "授权范围内令牌过期店铺数",
    "ods_rows_in_token_expired_scope": "令牌过期范围 ODS 记录数",
    "top_shop_hashes": "店铺哈希样例",
    "authorization_unexpired_shops": "授权未过期店铺数",
    "live_token_shops": "可调用凭据店铺数",
    "unverified_target_rows": "未覆盖目标记录数",
}

VALUE_LABELS = {
    "PASS": "通过",
    "WARN": "预警",
    "FAIL": "失败",
    "BLOCKED": "阻塞",
    "N/A": "不适用",
    "dwd_minus_ods": "DWD 有、ODS 无",
    "ods_minus_dwd": "ODS 有、DWD 无",
}

INLINE_STATUS_LABELS = {
    "PASS": "通过（PASS）",
    "WARN": "预警（WARN）",
    "FAIL": "失败（FAIL）",
    "BLOCKED": "阻塞（BLOCKED）",
}

DISPLAY_TERMS = "应用密钥（app_secret）|应用标识（app_key）|通过（PASS）|预警（WARN）|失败（FAIL）|阻塞（BLOCKED）"


class Safe(str):
    pass


def safe(value: str) -> Safe:
    return Safe(value)


def h(value: Any) -> str:
    if value is None:
        return "-"
    return html.escape(str(value), quote=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def should_scrub_key(key_name: str) -> bool:
    normalized = key_name.lower()
    if normalized in SENSITIVE_EXACT_KEYS:
        return True
    if "token" in normalized and SAFE_TOKEN_STAT_RE.search(normalized):
        return False
    return bool(SENSITIVE_KEY_RE.search(key_name))


def scrub(value: Any, key_name: str = "") -> Any:
    if should_scrub_key(key_name):
        return "***脱敏***"
    if isinstance(value, dict):
        return {key: scrub(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item, key_name) for item in value]
    return value


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def status_from_conclusion(value: Any) -> str:
    if isinstance(value, dict):
        status = str(value.get("status") or value.get("overall_status") or "").upper()
    else:
        status = str(value or "").strip().split(":", 1)[0].split("：", 1)[0].upper()
    return status if status in {"PASS", "WARN", "FAIL", "BLOCKED"} else "WARN"


def badge(status: Any) -> Safe:
    normalized = str(status or "N/A").upper()
    css = {
        "PASS": "pass",
        "WARN": "warn",
        "FAIL": "fail",
        "BLOCKED": "blocked",
        "N/A": "na",
    }.get(normalized, "na")
    return safe(f'<span class="badge {css}">{h(VALUE_LABELS.get(normalized, normalized))}</span>')


def display_key(key: Any) -> str:
    text = str(key)
    return KEY_LABELS.get(text, text)


def clean_display_text(text: str) -> str:
    text = re.sub(rf"\s+({DISPLAY_TERMS})", r"\1", text)
    text = re.sub(rf"({DISPLAY_TERMS})\s+(?=[一-鿿，。；：、）])", r"\1", text)
    return text


def display_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        text = re.sub(r"(?<![（(])\bapp_secret\b(?![）)])", "应用密钥（app_secret）", value)
        text = re.sub(r"(?<![（(])\bapp_key\b(?![）)])", "应用标识（app_key）", text)
        if value in VALUE_LABELS:
            return VALUE_LABELS[value]
        upper = value.upper()
        if upper in VALUE_LABELS:
            return VALUE_LABELS[upper]
        for status, label in VALUE_LABELS.items():
            if value.startswith(f"{status}：") or value.startswith(f"{status}:"):
                text = re.sub(rf"^{re.escape(status)}[：:]", f"{label}：", text, count=1)
                for inline_status, inline_label in INLINE_STATUS_LABELS.items():
                    text = re.sub(rf"(?<![（(])\b{inline_status}\b(?![）)])", inline_label, text)
                return clean_display_text(text)
        for inline_status, inline_label in INLINE_STATUS_LABELS.items():
            text = re.sub(rf"(?<![（(])\b{inline_status}\b(?![）)])", inline_label, text)
        return clean_display_text(text)
    return value


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def shorten_text(value: Any, limit: int = 220) -> str:
    if value is None:
        return "-"
    text = str(display_scalar(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def localize_for_display(value: Any) -> Any:
    if isinstance(value, dict):
        return {display_key(key): localize_for_display(item) for key, item in value.items()}
    if isinstance(value, list):
        return [localize_for_display(item) for item in value]
    return display_scalar(value)


def value_brief(value: Any) -> str:
    if isinstance(value, list):
        return f"{len(value)} 项"
    if isinstance(value, dict):
        return f"{len(value)} 项"
    return shorten_text(value, 160)


def record_summary(record: dict[str, Any], max_parts: int = 5) -> str:
    preferred = [
        "blocked_item",
        "gap_item",
        "status",
        "result",
        "reason",
        "impact",
        "impact_scope",
        "attempt",
        "timeout_seconds",
        "count",
        "rows",
        "field_difference_count",
    ]
    parts: list[str] = []
    used: set[str] = set()
    for key in preferred:
        if key in record and record[key] not in (None, ""):
            parts.append(f"{display_key(key)}：{value_brief(record[key])}")
            used.add(key)
        if len(parts) >= max_parts:
            break
    if len(parts) < max_parts:
        for key, value in record.items():
            if key in used or key == "evidence":
                continue
            parts.append(f"{display_key(key)}：{value_brief(value)}")
            if len(parts) >= max_parts:
                break
    return "；".join(parts) if parts else "见结构化 JSON 明细"


def compact_value_html(value: Any, max_items: int = 8) -> Safe:
    if isinstance(value, dict):
        if not value:
            return safe("无")
        rows = []
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                break
            rows.append(
                f'<li><span class="kv-key">{h(display_key(key))}</span>：{h(value_brief(item))}</li>'
            )
        more = ""
        if len(value) > max_items:
            more = f'<div class="note">另有 {h(len(value) - max_items)} 项未在主报告展开，详见结构化 JSON 明细。</div>'
        return safe(f'<ul class="compact-list">{"".join(rows)}</ul>{more}')
    if isinstance(value, list):
        if not value:
            return safe("无")
        scalar_items = [item for item in value if is_scalar(item)]
        if len(scalar_items) == len(value):
            chips = "".join(f"<code>{h(shorten_text(item, 80))}</code>" for item in scalar_items[:max_items])
            more = ""
            if len(value) > max_items:
                more = f'<div class="note">共 {h(len(value))} 项，另有 {h(len(value) - max_items)} 项见结构化 JSON 明细。</div>'
            return safe(f'<div class="chip-list">{chips}</div>{more}')
        rows = []
        for item in value[:max_items]:
            if isinstance(item, dict):
                rows.append(f"<li>{h(record_summary(item))}</li>")
            else:
                rows.append(f"<li>{h(value_brief(item))}</li>")
        more = ""
        if len(value) > max_items:
            more = f'<div class="note">共 {h(len(value))} 项，另有 {h(len(value) - max_items)} 项见结构化 JSON 明细。</div>'
        return safe(f'<ul class="compact-list">{"".join(rows)}</ul>{more}')
    return safe(h(display_scalar(value)))


def conclusion_summary_text(value: Any) -> str:
    if isinstance(value, dict):
        return shorten_text(
            value.get("summary")
            or value.get("reason")
            or value.get("conclusion")
            or value.get("status")
            or "未提供结论。",
            360,
        )
    return shorten_text(value or "未提供结论。", 360)


def cell(value: Any) -> str:
    if isinstance(value, Safe):
        return str(value)
    if isinstance(value, (dict, list)):
        return str(compact_value_html(localize_for_display(value)))
    return h(display_scalar(value))


def table(headers: list[str], rows: list[list[Any]], wrapper_class: str = "table-wrap") -> str:
    if not rows:
        rows = [["-", "无"]]
    if len(headers) == 2 and "table-meta" not in wrapper_class and "table-scroll" not in wrapper_class:
        wrapper_class = f"{wrapper_class} table-meta"
    head = "".join(f"<th>{h(header)}</th>" for header in headers)
    body = []
    for row in rows:
        fixed = list(row) + [""] * max(0, len(headers) - len(row))
        body.append("<tr>" + "".join(f"<td>{cell(value)}</td>" for value in fixed[: len(headers)]) + "</tr>")
    return f'<div class="{h(wrapper_class)}"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def scroll_table(headers: list[str], rows: list[list[Any]]) -> str:
    return table(headers, rows, "table-wrap table-scroll")


def dict_rows(obj: Any) -> list[list[Any]]:
    if isinstance(obj, dict):
        return [[display_key(key), value] for key, value in obj.items()]
    if isinstance(obj, list):
        return [["列表项", item] for item in obj]
    return [["说明", obj if obj not in (None, "") else "-"]]


def count_items(value: Any) -> Any:
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("count", "total", "rows", "rows_total", "mismatch_count", "missing_count"):
            if key in value:
                return value[key]
        if "status" in value:
            return value["status"]
        return len(value)
    if isinstance(value, str):
        return value
    return 1


def first_number(obj: Any, keys: list[str], default: Any = "-") -> Any:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj:
                return obj[key]
    return default


def build_field_rows(data: dict[str, Any]) -> list[list[Any]]:
    items = as_list(pick(data, "field_accuracy_details", "field_accuracy_summary", default=[]))
    rows: list[list[Any]] = []
    for item in items[:200]:
        if not isinstance(item, dict):
            rows.append(["-", "-", "-", "-", "-", "-", badge("WARN"), item])
            continue
        status = item.get("status") or item.get("result") or "N/A"
        rows.append(
            [
                item.get("target_field") or item.get("field") or item.get("field_name") or "-",
                item.get("field_role") or item.get("accuracy_scope") or "-",
                item.get("field_category") or item.get("category") or "-",
                item.get("expected_assignment_rule") or item.get("expected_rule") or item.get("assignment_rule") or "-",
                item.get("actual_validation_rule") or item.get("validation_method") or item.get("actual_rule") or "-",
                item.get("checked_count") if item.get("checked_count") is not None else "-",
                item.get("mismatched_count") if item.get("mismatched_count") is not None else "-",
                badge(status),
                item.get("difference_note") or item.get("note") or "-",
            ]
        )
    return rows


def build_source_not_persisted_rows(data: dict[str, Any]) -> list[list[Any]]:
    items = as_list(data.get("source_fields_not_persisted"))
    rows: list[list[Any]] = []
    for item in items[:200]:
        if not isinstance(item, dict):
            rows.append(["-", "-", "-", badge("WARN"), item])
            continue
        status = item.get("status") or item.get("result") or "N/A"
        rows.append(
            [
                item.get("source_field") or item.get("source_field_name") or item.get("field") or "-",
                item.get("source_field_path") or item.get("source_field_origin") or item.get("source") or "-",
                item.get("target_field") or item.get("target_field_match") or "-",
                badge(status),
                item.get("reason") or item.get("note") or item.get("required_evidence") or "-",
            ]
        )
    return rows


def sample_empty_note(samples: list[Any]) -> str:
    dict_samples = [item for item in samples if isinstance(item, dict)]
    if not dict_samples:
        return "见 JSON 明细"
    source_non_empty = [item.get("source_is_empty") in (False, "否", "false", "False", 0) for item in dict_samples]
    target_empty = [item.get("target_is_empty") in (True, "是", "true", "True", 1) for item in dict_samples]
    if source_non_empty and all(source_non_empty) and target_empty and all(target_empty):
        return "源有值，目标为空"
    source_empty = [item.get("source_is_empty") in (True, "是", "true", "True", 1) for item in dict_samples]
    target_non_empty = [item.get("target_is_empty") in (False, "否", "false", "False", 0) for item in dict_samples]
    if source_empty and all(source_empty) and target_non_empty and all(target_non_empty):
        return "源为空，目标有值"
    return "源目标值不一致"


def empty_state_text(value: Any, side: str) -> str:
    if value in (True, "是", "true", "True", 1):
        return f"{side}为空"
    if value in (False, "否", "false", "False", 0):
        return f"{side}有值"
    return f"{side}空值状态未知"


def sample_hash_note(sample: dict[str, Any]) -> str:
    parts: list[str] = []
    business_key_hash = sample.get("business_key_hash") or sample.get("key_hash")
    if business_key_hash:
        parts.append(f'业务键哈希 <code>{h(business_key_hash)}</code>')
    parts.append(h(empty_state_text(sample.get("source_is_empty"), "源")))
    source_value_hash = sample.get("source_value_hash")
    if source_value_hash:
        parts.append(f'源值哈希 <code>{h(source_value_hash)}</code>')
    parts.append(h(empty_state_text(sample.get("target_is_empty"), "目标")))
    target_value_hash = sample.get("target_value_hash")
    if target_value_hash:
        parts.append(f'目标值哈希 <code>{h(target_value_hash)}</code>')
    return "；".join(parts) if parts else "样例见结构化 JSON 明细"


def sample_value_text(sample: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in sample:
            raw_value = sample.get(key)
            if raw_value is None:
                value = "NULL"
            elif raw_value == "":
                value = "空字符串"
            else:
                value = display_scalar(raw_value)
            return shorten_text(value, 160)
    return ""


def sample_readable_note(sample: dict[str, Any]) -> str:
    business_key = sample_value_text(sample, "business_key", "key", "business_key_text", "source_id", "target_id")
    expected_value = sample_value_text(sample, "expected_value", "source_value", "expected")
    actual_value = sample_value_text(sample, "actual_value", "target_value", "actual")
    if business_key and expected_value and actual_value:
        return (
            f'<span class="sample-kv">业务键：<code>{h(business_key)}</code></span>'
            f'<span class="sample-kv">预期值：<code>{h(expected_value)}</code></span>'
            f'<span class="sample-kv">实际值：<code>{h(actual_value)}</code></span>'
        )
    return sample_hash_note(sample)


def field_sample_html(samples: list[Any], max_examples: int = 3) -> str:
    dict_samples = [item for item in samples if isinstance(item, dict)]
    if not dict_samples:
        return '<div class="diff-sample-note">样例见结构化 JSON 明细。</div>'
    items = []
    for index, sample in enumerate(dict_samples[:max_examples], start=1):
        items.append(f"<li>样例{index}：{sample_readable_note(sample)}</li>")
    more = ""
    if len(dict_samples) > max_examples:
        more = f'<div class="diff-sample-note">每个字段最多展示 {h(max_examples)} 条样例，其余样例见结构化 JSON 明细。</div>'
    return f'<ol class="diff-samples">{"".join(items)}</ol>{more}'


def grouped_field_difference_items(raw_items: list[Any], max_samples_per_field: int = 3) -> list[dict[str, Any]]:
    ready_items: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        nested_samples = as_list(item.get("samples")) if "samples" in item else []
        if nested_samples:
            normalized = dict(item)
            normalized["samples"] = nested_samples
            if normalized.get("mismatch_count") is None:
                normalized["mismatch_count"] = len([sample for sample in nested_samples if isinstance(sample, dict)])
            ready_items.append(normalized)
            continue
        field = str(item.get("difference_field") or item.get("field") or "-")
        interface_path = str(item.get("interface_path") or "-")
        interface_name = str(item.get("interface_name") or "-")
        key = (interface_path, field)
        if key not in grouped:
            grouped[key] = {
                "interface_name": interface_name,
                "interface_path": interface_path,
                "difference_field": field,
                "difference_type": item.get("difference_type") or "字段值不一致",
                "mismatch_count": 0,
                "samples": [],
            }
        grouped_item = grouped[key]
        grouped_item["mismatch_count"] = int(grouped_item.get("mismatch_count") or 0) + 1
        if len(grouped_item["samples"]) >= max_samples_per_field:
            continue
        grouped_item["samples"].append(
            {
                "business_key": item.get("business_key"),
                "source_id": item.get("source_id"),
                "target_id": item.get("target_id") or item.get("staging_id"),
                "difference_type": item.get("difference_type") or "字段值不一致",
                "difference_field": field,
                "expected_value": item.get("expected_value", item.get("source_value")),
                "actual_value": item.get("actual_value", item.get("target_value")),
                "source_value": item.get("source_value"),
                "target_value": item.get("target_value"),
                "difference_note": item.get("difference_note") or item.get("note"),
            }
        )
    grouped_items = sorted(
        grouped.values(),
        key=lambda item: (str(item.get("interface_name") or ""), str(item.get("difference_field") or "")),
    )
    return ready_items + grouped_items


def compact_diff_summary(key: str, value: Any) -> Any:
    if not value:
        return "无"
    if not isinstance(value, dict):
        return value
    status = value.get("status") or value.get("result") or "N/A"
    reason = value.get("reason") or value.get("note") or "-"
    count = count_items(value)
    if key == "field_differences":
        field_items = grouped_field_difference_items(as_list(value.get("samples")))
        field_count = value.get("field_count") if value.get("field_count") is not None else len(field_items)
        items_html: list[str] = []
        for item in field_items[:12]:
            field_name = item.get("difference_field") or item.get("field") or "-"
            interface_name = item.get("interface_name")
            field_label = f"{interface_name} / {field_name}" if interface_name not in (None, "", "-") else field_name
            mismatch_count = item.get("mismatch_count") if item.get("mismatch_count") is not None else "-"
            samples = as_list(item.get("samples"))
            note = sample_empty_note(samples)
            items_html.append(
                "<li>"
                f'<div class="diff-field-line"><code>{h(field_label)}</code>：{h(display_scalar(mismatch_count))} 条；{h(note)}</div>'
                f"{field_sample_html(samples)}"
                "</li>"
            )
        if not items_html and count not in (0, "0", None, ""):
            items_html.append("<li>存在字段差异，完整字段样例见结构化 JSON 明细。</li>")
        more = ""
        if len(field_items) > 12:
            more = f"<div class=\"note\">另有 {h(len(field_items) - 12)} 个字段未在主表展开。</div>"
        if not items_html:
            items_html.append("<li>未发现字段值不一致。</li>")
        return safe(
            "<div class=\"diff-summary\">"
            f"<div>状态：{badge(status)}；差异字段数：{h(display_scalar(field_count))}；差异记录数：{h(display_scalar(count))}</div>"
            f"<div class=\"note\">原因：{h(display_scalar(reason))}</div>"
            f"<div class=\"diff-scroll\"><ul class=\"diff-list\">{''.join(items_html)}</ul></div>"
            f"{more}"
            "<div class=\"note\">每个字段最多展示 3 条可读样例；完整样例保留在结构化 JSON 明细，主报告不展开原始 JSON。</div>"
            "</div>"
        )
    samples = as_list(value.get("samples"))
    sample_hashes: list[str] = []
    for sample in samples[:8]:
        if isinstance(sample, dict):
            sample_hash = sample.get("business_key_hash") or sample.get("key_hash") or sample.get("source_id") or sample.get("target_id")
            if sample_hash:
                sample_hashes.append(str(sample_hash))
    sample_html = ""
    if sample_hashes:
        joined = "、".join(f"<code>{h(item)}</code>" for item in sample_hashes)
        sample_html = f"<div>样例业务键：{joined}</div>"
    elif count in (0, "0"):
        sample_html = "<div>未发现该类差异。</div>"
    else:
        sample_html = "<div>样例见结构化 JSON 明细。</div>"
    return safe(
        "<div class=\"diff-summary\">"
        f"<div>状态：{badge(status)}；数量：{h(display_scalar(count))}</div>"
        f"<div class=\"note\">原因：{h(display_scalar(reason))}</div>"
        f"{sample_html}"
        "</div>"
    )


def build_diff_rows(data: dict[str, Any]) -> list[list[Any]]:
    totals = data.get("totals_summary") or {}
    uniqueness = data.get("uniqueness_summary") or {}
    groups = [
        ("源有目标无", "missing_in_target", totals, ["missing_count", "source_missing_count"]),
        ("目标有源无", "extra_in_target", totals, ["extra_count", "target_extra_count"]),
        ("目标重复", "duplicate_in_target", uniqueness, ["duplicate_count", "target_duplicate_count"]),
        ("字段值不一致", "field_differences", totals, ["field_difference_count", "field_diff_count"]),
    ]
    rows: list[list[Any]] = []
    for label, key, fallback_obj, fallback_keys in groups:
        value = data.get(key)
        quantity = count_items(value)
        if quantity == 0:
            quantity = first_number(fallback_obj, fallback_keys, 0)
        rows.append([label, quantity, compact_diff_summary(key, scrub(value))])
    return rows


def build_blocked_rows(data: dict[str, Any]) -> list[list[Any]]:
    items = as_list(data.get("blocked_items"))
    if not items:
        return [["无阻塞项", badge("PASS"), "未记录阻塞项。", "-", "-"]]
    rows: list[list[Any]] = []
    for item in items:
        if not isinstance(item, dict):
            rows.append(["阻塞项", badge("BLOCKED"), item, "-", "-"])
            continue
        status = item.get("status") or item.get("result") or "BLOCKED"
        rows.append(
            [
                item.get("blocked_item") or item.get("item") or "-",
                badge(status),
                item.get("reason") or item.get("note") or "-",
                item.get("impact") or item.get("impact_scope") or "-",
                compact_value_html(localize_for_display(item.get("current_evidence") or item.get("evidence")))
                if (item.get("current_evidence") or item.get("evidence")) not in (None, "")
                else "见结构化 JSON 明细",
            ]
        )
    return rows


def build_coverage_gap_rows(data: dict[str, Any]) -> list[list[Any]]:
    items = as_list(data.get("coverage_gaps"))
    if not items:
        return [["无覆盖缺口", badge("PASS"), "未记录覆盖缺口。", "-", "-"]]
    rows: list[list[Any]] = []
    for item in items:
        if not isinstance(item, dict):
            rows.append(["覆盖缺口", badge("WARN"), item, "-", "-"])
            continue
        status = item.get("status") or item.get("result") or "WARN"
        evidence = item.get("current_evidence") or item.get("evidence")
        rows.append(
            [
                item.get("gap_item") or item.get("item") or "-",
                badge(status),
                item.get("reason") or item.get("note") or "-",
                compact_value_html(localize_for_display(evidence)) if evidence not in (None, "") else "见结构化 JSON 明细",
                item.get("impact_scope") or item.get("impact") or "-",
            ]
        )
    return rows


def build_recommendation_rows(data: dict[str, Any]) -> list[list[Any]]:
    items = as_list(data.get("recommendations"))
    if not items:
        return [["P1", "补齐覆盖缺口后复跑迁移核验", "保证源目标完整性、准确性和结论可追溯"]]
    rows: list[list[Any]] = []
    for item in items:
        if isinstance(item, dict):
            rows.append([item.get("priority") or "-", item.get("action") or item.get("recommendation") or "-", item.get("expected_benefit") or item.get("benefit") or "-"])
        else:
            rows.append(["-", item, "-"])
    return rows


def render_page(title: str, subtitle: str, body: str) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    footer = f"生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}；报告类型：直连数据迁移核验"
    return (
        template.replace("{{title}}", h(title))
        .replace("{{subtitle}}", h(subtitle))
        .replace("{{body}}", body)
        .replace("{{footer}}", h(footer))
    )


def render_main(data: dict[str, Any], html_path: Path, detail_html: Path | None, detail_json: Path | None, title: str) -> str:
    status = status_from_conclusion(data.get("conclusion"))
    totals = data.get("totals_summary") or {}
    uniqueness = data.get("uniqueness_summary") or {}
    source_rows = first_number(totals, ["source_rows", "source_count", "source_total", "rows_source"])
    target_rows = first_number(totals, ["target_rows", "target_count", "target_total", "rows_target"])
    missing_count = count_items(data.get("missing_in_target")) or first_number(totals, ["missing_count"], 0)
    extra_count = count_items(data.get("extra_in_target")) or first_number(totals, ["extra_count"], 0)
    duplicate_count = count_items(data.get("duplicate_in_target")) or first_number(uniqueness, ["duplicate_count", "target_duplicate_count"], 0)
    field_diff_count = count_items(data.get("field_differences"))
    detail_href = None
    if detail_html:
        detail_href = Path(os.path.relpath(detail_html, html_path.parent)).as_posix()
    summary_rows = [
        ["总体状态", badge(status), conclusion_summary_text(data.get("conclusion"))],
        ["是否需要研发修复", badge("FAIL" if status == "FAIL" else "N/A"), "仅当存在成立的数据缺失、额外、重复或关键字段错误时需要研发修复；覆盖不足优先补证复跑。"],
        ["是否存在阻塞", badge("BLOCKED" if data.get("blocked_items") else "PASS"), f"阻塞项 {count_items(data.get('blocked_items'))} 个。"],
    ]
    evidence_rows = [
        ["结构化 JSON 明细", safe(f"<code>{h(detail_json)}</code>") if detail_json else "-"],
        ["证据 HTML", safe(f'<a href="{h(detail_href)}">查看证据页</a>') if detail_href else "未生成独立证据页"],
    ]
    body = f"""
    <section>
      <h2>执行摘要</h2>
      <p>{h(conclusion_summary_text(data.get("conclusion")))}</p>
      <div class="summary">
        <div class="metric"><div class="label">源记录数</div><div class="value">{h(display_scalar(source_rows))}</div></div>
        <div class="metric"><div class="label">目标记录数</div><div class="value">{h(display_scalar(target_rows))}</div></div>
        <div class="metric"><div class="label">缺失/额外/重复</div><div class="value">{h(display_scalar(missing_count))}/{h(display_scalar(extra_count))}/{h(display_scalar(duplicate_count))}</div></div>
        <div class="metric"><div class="label">字段差异</div><div class="value">{h(display_scalar(field_diff_count))}</div></div>
        <div class="metric"><div class="label">总体状态</div><div class="value">{badge(status)}</div></div>
      </div>
      {table(["结论项", "状态", "说明"], summary_rows)}
    </section>
    <section>
      <h2>迁移范围与口径</h2>
      {table(["项", "内容"], dict_rows(data.get("verification_scope")))}
    </section>
    <section>
      <h2>源基线证据</h2>
      {table(["项", "内容"], dict_rows(data.get("source_baseline")))}
    </section>
    <section>
      <h2>目标来源证据</h2>
      {table(["项", "内容"], dict_rows(pick(data, "target_sources", "target_source", default={})))}
    </section>
    <section>
      <h2>业务键与匹配策略</h2>
      {table(["项", "内容"], dict_rows(data.get("business_keys")))}
    </section>
    <section>
      <h2>完整性核验</h2>
      {table(["项", "内容"], dict_rows(data.get("totals_summary")))}
      {table(["唯一性项", "内容"], dict_rows(data.get("uniqueness_summary")))}
    </section>
    <section>
      <h2>准确性核验</h2>
      {scroll_table(["目标字段", "字段角色", "字段类别", "预期赋值/生成规则", "实际核验规则", "检查记录数", "不匹配记录数", "状态", "说明"], build_field_rows(data))}
    </section>
    <section>
      <h2>接口字段未入库说明</h2>
      <p class="note">本区用于说明源接口提供但目标表未承载的字段；若源接口字段清单未结构化采集，必须明确标记为阻塞或待补充，不能用目标表字段反推接口字段。</p>
      {table(["源接口字段", "接口路径/来源", "入库目标字段", "状态", "说明"], build_source_not_persisted_rows(data))}
    </section>
    <section>
      <h2>差异与阻塞</h2>
      {table(["差异类型", "数量", "样例/说明"], build_diff_rows(data))}
      {table(["阻塞项", "状态", "原因", "影响", "证据摘要"], build_blocked_rows(data))}
    </section>
    <section>
      <h2>覆盖缺口与风险</h2>
      {table(["覆盖缺口", "状态", "原因", "当前证据摘要", "影响范围"], build_coverage_gap_rows(data))}
    </section>
    <section>
      <h2>整改建议与复跑条件</h2>
      {table(["优先级", "建议动作", "预期收益"], build_recommendation_rows(data))}
    </section>
    <section>
      <h2>附录与证据</h2>
      {table(["证据项", "路径/说明"], evidence_rows)}
    </section>
    """
    subtitle = f"链路类型：源 -> 目标；总体状态：{VALUE_LABELS.get(status, status)}"
    return render_page(title, subtitle, body)


def render_detail(data: dict[str, Any], title: str) -> str:
    body = f"""
    <section>
      <h2>字段准确性明细</h2>
      {scroll_table(["目标字段", "字段角色", "字段类别", "预期赋值/生成规则", "实际核验规则", "检查记录数", "不匹配记录数", "状态", "说明"], build_field_rows(data))}
    </section>
    <section>
      <h2>接口字段未入库明细</h2>
      {table(["源接口字段", "接口路径/来源", "入库目标字段", "状态", "说明"], build_source_not_persisted_rows(data))}
    </section>
    <section>
      <h2>差异样例明细</h2>
      {table(["差异类型", "数量", "样例/说明"], build_diff_rows(data))}
    </section>
    <section>
      <h2>覆盖缺口明细</h2>
      {table(["覆盖缺口", "状态", "原因", "当前证据摘要", "影响范围"], build_coverage_gap_rows(data))}
    </section>
    <section>
      <h2>阻塞项明细</h2>
      {table(["阻塞项", "状态", "原因", "影响", "证据摘要"], build_blocked_rows(data))}
    </section>
    """
    return render_page(f"{title} - 证据明细", "直连迁移核验证据页", body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成直连数据迁移 HTML 报告")
    parser.add_argument("--input", required=True, type=Path, help="结构化核验 JSON")
    parser.add_argument("--html", required=True, type=Path, help="输出主 HTML 路径")
    parser.add_argument("--detail-json", required=True, type=Path, help="输出结构化 JSON 明细路径")
    parser.add_argument("--detail-html", type=Path, default=None, help="可选输出证据 HTML 路径")
    parser.add_argument("--title", default="直连数据迁移核验报告", help="报告标题")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = load_json(args.input)
    if not isinstance(raw, dict):
        raise SystemExit("输入 JSON 顶层必须是对象。")
    data = scrub(raw)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.detail_json.parent.mkdir(parents=True, exist_ok=True)
    args.detail_json.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if args.detail_html:
        args.detail_html.parent.mkdir(parents=True, exist_ok=True)
        args.detail_html.write_text(render_detail(data, args.title), encoding="utf-8")
    args.html.write_text(render_main(data, args.html, args.detail_html, args.detail_json, args.title), encoding="utf-8")
    print(json.dumps({"html": str(args.html), "detail_json": str(args.detail_json), "detail_html": str(args.detail_html) if args.detail_html else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
