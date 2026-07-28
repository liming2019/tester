#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_INTERFACE_NAME = "默认接口"
MAIN_REPORT_STATUSES = {"PASS", "BLOCKED", "FAIL"}

DISPLAY_LABELS = {
    "migration_object": "迁移对象",
    "verification_type": "核验类型",
    "business_module": "业务模块",
    "batch_scope": "批次范围",
    "environment_scope": "环境范围",
    "time_filter_rule": "时间筛选口径",
    "object_counts": "对象统计",
    "requested_interfaces": "请求接口",
    "supplement_interfaces": "补充接口",
    "report_generated_at": "报告生成时间",
    "source_time_window": "源时间窗口",
    "batch_execution_windows": "批次执行窗口",
    "source_actual_range_note": "源侧实际范围说明",
    "target_actual_range_note": "目标侧实际范围说明",
    "relation_start_date": "关系起始日期",
    "relation_end_date": "关系结束日期",
    "relation_request_batches": "关系请求批次",
    "request_video_count": "请求视频数",
    "response_group_count": "返回分组数",
    "requested_interface_overview": "请求接口概述",
    "actual_baseline_strategy": "实际基线策略",
    "baseline_limitations": "基线限制",
    "runtime_account": "运行账号",
    "account_key_masked": "账号键脱敏值",
    "request_id": "请求 ID",
    "auth_request_id": "鉴权请求流水号",
    "live_request_summary": "源接口回查汇总",
    "request_parameter_summary": "请求参数口径",
    "request_batch_count": "请求批次数",
    "failure_batch_count": "失败批次数",
    "missing_video_count": "未返回素材数",
    "sample_request_ids": "请求流水号样例",
    "method": "请求方法",
    "videoType": "视频类型",
    "videoIds": "视频 ID 过滤方式",
    "primary_isInner": "首轮查询",
    "retry_isInner": "未命中重试",
    "sensitive_params": "敏感参数处理",
    "missing_video_samples": "未返回素材样例",
    "old_video_id": "旧系统 videoId",
    "migration_map_id": "迁移映射记录ID",
    "target_media_id": "目标 media_id",
    "material_name": "素材名称",
    "lookup_result": "回查结果",
    "impact": "影响",
    "batch_index": "批次序号",
    "result_layer": "结果层",
    "account": "账号",
    "collection_batches": "合集批次",
    "batch_id": "批次 ID",
    "stage": "阶段",
    "content_code": "内容编码",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "tables": "涉及表",
    "summary": "摘要",
    "database": "数据库",
    "database_alias": "数据库别名",
    "source_type": "源类型",
    "actual_source_field_total": "源字段总数",
    "mapped_field_total": "已纳入规则字段数",
    "na_field_total": "N/A 字段数",
    "explicitly_uncollected_field_total": "未采集字段数",
    "unmapped_field_total": "未纳入规则字段数",
    "documented_expected_field_total": "文档预期字段数",
    "documented_expected_fields": "文档预期字段",
    "documented_field_summary": "接口文档字段摘要",
    "documented_missing_but_actual_used": "文档未列但实际核验使用字段",
    "live_actual_only_field_total": "实际响应独有字段数",
    "undocumented_validation_field_total": "实际核验使用但文档未列字段数",
    "rule_basis_blocked_field_total": "规则依据阻塞字段数",
    "rule_basis_gate_passed": "规则依据准入通过",
    "gate_passed": "准入校验通过",
    "note": "说明",
    "item": "阻塞项",
    "detail": "详情",
    "type": "类型",
    "interface_name": "接口名称",
    "interface_path": "接口路径",
    "actual_source_fields": "实际源字段",
    "mapped_fields": "已纳入规则字段",
    "na_fields": "N/A 字段",
    "explicitly_uncollected_fields": "未采集字段",
    "unmapped_fields": "未纳入规则字段",
    "field_name": "字段名",
    "reason": "原因",
    "current_status": "当前状态",
    "suggested_action": "建议动作",
    "needed_action": "建议动作",
    "source_fields": "源字段",
    "target_fields": "目标字段",
    "field_meaning": "字段含义",
    "assignment_type": "赋值方式",
    "rule_expression": "赋值规则",
    "null_strategy": "空值策略",
    "rule_source": "规则来源",
    "is_key_field": "是否关键字段",
    "in_accuracy_validation": "纳入准确性核验",
    "acceptance_standard": "验收标准",
    "source_field_group": "源字段分组",
    "target_field_group": "目标字段分组",
    "target_field": "目标字段",
    "field_category": "字段分类",
    "acceptance_level": "验收级别",
    "validation_level": "核验级别",
    "validation_method": "核验方式",
    "validated_records": "已核验记录数",
    "matched_records": "匹配记录数",
    "mismatched_records": "不匹配记录数",
    "null_anomaly_records": "空值异常记录数",
    "transform_failed_records": "转换失败记录数",
    "consistency_rate": "一致率",
    "affected_records": "影响记录数",
    "result": "结果",
    "difference_note": "差异说明",
    "checked_count": "检查记录数",
    "matched_count": "匹配记录数",
    "mismatched_count": "不匹配记录数",
    "gap_item": "覆盖缺口项",
    "current_evidence": "当前证据",
    "impact_scope": "影响范围",
    "business_key": "业务键",
    "source_id": "源标识",
    "staging_id": "中间层标识",
    "staging_evidence": "中间层证据",
    "target_id": "目标标识",
    "difference_type": "差异类型",
    "difference_field": "差异字段",
    "source_value": "源值",
    "target_value": "目标值",
    "group": "分组",
    "business_domain": "业务域",
    "priority": "优先级",
    "stage1": "阶段一",
    "stage2": "阶段二",
    "full_chain": "全链路",
    "field_accuracy": "字段准确性",
    "coverage_status": "覆盖状态",
    "conclusion": "结论",
    "short": "简要结论",
    "must_fix_exists": "是否存在必须修复问题",
    "must_fix_note": "必须修复说明",
    "next_action": "下一步动作",
    "overview": "概述",
    "description": "说明",
    "remark": "备注",
    "items": "明细项",
    "status": "状态",
    "failure_reason": "失败原因",
    "failure_summary": "失败摘要",
    "root_cause": "根因",
    "key_field_total": "关键字段总数",
    "baseline_field_total": "已有规则基线字段数",
    "accuracy_validated_field_total": "已完成准确性核验字段数",
    "pass_field_total": "PASS 字段数",
    "warn_field_total": "WARN 字段数",
    "fail_field_total": "FAIL 字段数",
    "blocked_field_total": "BLOCKED 字段数",
    "na_field_total": "N/A 字段数",
}

LONG_TEXT_HEADERS = {
    "内容",
    "说明",
    "明细",
    "核验摘要",
    "差异说明",
    "原因",
    "当前证据",
    "影响范围",
    "赋值规则",
    "预期赋值规则",
    "实际核验规则",
    "规则来源",
    "中间层/规则依据",
    "空值策略",
    "空值/异常处理",
    "验收标准",
    "详情",
}
FIELD_LIST_HEADERS = {
    "实际源字段",
    "已纳入规则字段",
    "N/A 字段",
    "未采集字段",
    "未纳入规则字段",
    "文档预期字段",
    "实际响应独有字段",
    "中间层独有字段",
    "源字段",
    "来源字段",
    "目标字段",
}
PRIMARY_FIELD_LIST_HEADERS = {"实际源字段", "已纳入规则字段", "N/A 字段"}
SECONDARY_FIELD_LIST_HEADERS = {"未采集字段", "未纳入规则字段"}
PATH_HEADERS = {"接口路径"}
STATUS_HEADERS = {"状态", "当前状态", "覆盖状态", "阶段一", "阶段二", "全链路", "字段准确性"}
ACTION_HEADERS = {"明细页", "查看"}
SOURCE_NAME_HEADERS = {"源接口名称"}
COUNT_HEADERS = {"源字段总数", "检查记录数", "不匹配记录数", "字段数", "接口数"}
DB_FIELD_HEADERS = {"表字段"}
FIELD_NAME_HEADERS = {"字段名"}
ASSIGNMENT_TYPE_HEADERS = {"赋值方式"}
VALIDATION_LEVEL_HEADERS = {"核验级别"}

SOURCE_FIELD_ALIASES = {
    "videoId": "视频id",
    "advertiserId": "广告主id",
    "materialId": "素材id",
    "name": "名称",
    "type": "类型",
    "accountKey": "账号key",
    "accountName": "账号名称",
    "adminId": "管理员id",
    "advertiserName": "广告主名称",
    "avgClickCost": "平均点击成本",
    "avgPlayDuration3s": "3秒平均播放时长",
    "avgValidPlayCost": "平均有效播放成本",
    "clickCnt": "点击次数",
    "clickRate": "点击率",
    "companyId": "公司id",
    "convertCnt": "转化次数",
    "convertCost": "转化成本",
    "convertRate": "转化率",
    "createTime": "创建时间",
    "dyComment": "抖音评论数",
    "dyLike": "抖音点赞数",
    "dyShare": "抖音分享数",
    "fileName": "文件名",
    "isExpired": "是否过期",
    "isNative": "是否原生视频",
    "isSysSync": "是否系统同步",
    "payOrderAmount": "支付订单金额",
    "payOrderCouponAmount": "支付订单优惠金额",
    "play25FeedBreak": "25%播放数",
    "play50FeedBreak": "50%播放数",
    "play75FeedBreak": "75%播放数",
    "playDuration3s": "3秒播放数",
    "playOver": "完播数",
    "relationId": "关系id",
    "roi": "投入产出比",
    "showCnt": "展示次数",
    "statCost": "统计花费",
    "totalPlay": "总播放量",
    "collectionId": "合集id",
}

TARGET_TABLE_ALIASES = {
    "view_migration_id_map": "迁移映射表",
    "view_migration_error": "迁移错误表",
    "view_media_annotation": "批注表",
    "view_media_reference": "成片引用关系表",
    "view_collection": "合集表",
    "media": "素材表",
    "user": "用户表",
    "view_migration_batch": "迁移批次表",
}

TARGET_FIELD_ALIASES = {
    "view_migration_id_map.old_id": "源业务键",
    "view_migration_id_map.new_id": "目标业务键",
    "view_media_annotation.id": "批注ID",
    "view_media_annotation.media_id": "所属素材ID",
    "view_media_annotation.content": "批注内容",
    "view_media_annotation.start_timestamp_ms": "开始时间毫秒",
    "view_media_annotation.end_timestamp_ms": "结束时间毫秒",
    "view_media_annotation.annotation_type": "批注类型",
    "view_media_annotation.create_by_name": "批注人名称",
    "view_media_annotation.create_by_user_id": "批注人ID",
    "view_media_annotation.mention_user_ids": "@人员ID",
    "view_media_annotation.parent_id": "父批注ID",
    "view_media_annotation.reply_to_id": "回复对象ID",
    "view_media_annotation.reply_to_name": "回复对象名称",
    "view_media_annotation.status": "状态",
    "view_media_annotation.del_flag": "删除标志",
    "view_media_annotation.create_by": "创建者",
    "view_media_annotation.create_time": "创建时间",
    "view_media_annotation.update_by": "更新者",
    "view_media_annotation.update_time": "更新时间",
    "view_media_annotation.tenant_id": "租户ID",
    "view_media_annotation.drawing_data": "视觉批注数据",
    "view_media_reference.id": "目标关系记录ID",
    "view_media_reference.del_flag": "删除标志",
    "view_media_reference.create_by": "创建者",
    "view_media_reference.create_time": "创建时间",
    "view_media_reference.update_by": "更新者",
    "view_media_reference.update_time": "更新时间",
    "view_media_reference.source_media_id": "引用方成片ID",
    "view_media_reference.ref_content_code": "关联业务标识",
    "view_media_reference.ref_watermark_code": "关联水印字符/溯源码",
    "view_media_reference.ref_version_group_id": "关联版本组ID",
    "view_media_reference.ref_media_id": "被引用素材ID",
    "view_media_reference.ref_media_duration": "被引用素材时长",
    "view_media_reference.duration": "引用具体时长",
    "view_media_reference.is_first": "是否首帧",
    "view_media_reference.tenant_id": "租户ID",
    "view_media_reference.type": "关联类型",
    "view_collection.id": "合集ID",
    "view_collection.name": "合集名称",
    "media.collection_id": "素材所属合集ID",
    "old_id": "源业务键",
    "new_id": "目标业务键",
    "id": "批注ID",
    "media_id": "所属素材ID",
    "content": "批注内容",
    "start_timestamp_ms": "开始时间毫秒",
    "end_timestamp_ms": "结束时间毫秒",
    "annotation_type": "批注类型",
    "create_by_name": "批注人名称",
    "create_by_user_id": "批注人ID",
    "mention_user_ids": "@人员ID",
    "parent_id": "父批注ID",
    "reply_to_id": "回复对象ID",
    "reply_to_name": "回复对象名称",
    "status": "状态",
    "del_flag": "删除标志",
    "create_by": "创建者",
    "create_time": "创建时间",
    "update_by": "更新者",
    "update_time": "更新时间",
    "tenant_id": "租户ID",
    "drawing_data": "视觉批注数据",
}

TARGET_SOURCE_FIELD_HINTS = {
    "old_id": ["videoid", "commentlistid", "id"],
    "new_id": ["videoid", "commentlistid", "id"],
    "id": ["videoid", "commentlistid", "id"],
    "media_id": ["videoid", "version"],
    "content": ["content", "resplistcontent"],
    "start_timestamp_ms": ["starttime"],
    "end_timestamp_ms": ["endtime"],
    "annotation_type": ["starttime", "endtime"],
    "create_by_name": ["accountname", "resplistaccountname"],
    "create_by_user_id": ["accountname", "accountid", "resplistaccountname", "resplistaccountid"],
    "mention_user_ids": ["receiveaccountname", "receiveaccountid"],
    "parent_id": ["resplist"],
    "reply_to_id": ["resplistrespaccountname", "resplistrespaccountid"],
    "reply_to_name": ["resplistrespaccountname"],
}

SOURCE_FIELD_ALIASES.update(
    {
        "commentList": "批注列表",
        "commentList.id": "批注ID",
        "commentList.version": "批注所属版本",
        "commentList.content": "批注内容",
        "commentList.startTime": "批注开始时间",
        "commentList.endTime": "批注结束时间",
        "commentList.accountName": "批注人名称",
        "commentList.accountId": "批注人账号ID",
        "commentList.receiveAccountName": "@人员名称",
        "commentList.receiveAccountId": "@人员账号ID",
        "commentList.respList": "回复列表",
        "commentList.respList.id": "回复ID",
        "commentList.respList.content": "回复内容",
        "commentList.respList.accountName": "回复人名称",
        "commentList.respList.respAccountName": "被回复人名称",
        "content": "批注/回复内容",
        "respList.content": "回复内容",
        "respList.id": "回复ID",
        "respList.accountName": "回复人名称",
        "respList.receiveAccountName": "@人员名称",
        "父批注.media_id": "父批注素材ID",
        "startTime": "批注开始时间",
        "endTime": "批注结束时间",
        "receiveAccountName": "@人员名称",
        "respList": "回复列表",
        "respList.respAccountName": "被回复人名称",
        "versionList.version": "素材版本号",
        "oneLevelVideoType": "一级视频分类",
        "twoLevelVideoType": "二级视频分类",
        "videoType": "视频类型",
        "videoUrl": "视频地址",
        "coverUrl": "封面地址",
        "viewCount": "播放次数",
        "downloadCount": "下载次数",
        "collectCount": "收藏次数",
    }
)


class RawHtml(str):
    pass


def default_contract_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "report_contract.json"


def default_template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "report_template.html"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def get_status(data: dict[str, Any]) -> str:
    conclusion = data.get("conclusion")
    if isinstance(conclusion, str):
        return conclusion
    if isinstance(conclusion, dict):
        for key in ("status", "result", "conclusion"):
            value = conclusion.get(key)
            if isinstance(value, str):
                return value
    return "BLOCKED"


def get_identity(item: Any, keys: list[str]) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def first_non_empty(item: Any, keys: list[str]) -> Any:
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
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
    normalized = stringify_short(requested).lower()
    if normalized in {"direct", "staged"}:
        return normalized

    for key in contract.get("chain_type_keys", []):
        value = stringify_short(data.get(key)).lower()
        if value in {"direct", "staged"}:
            return value
        if value in {"source_to_target", "source-target", "直连", "源到目标"}:
            return "direct"
        if value in {"two_stage", "three_stage", "staged_chain", "分阶段", "两阶段", "三阶段"}:
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


def slugify(text: str) -> str:
    compact = re.sub(r"\s+", "-", text.strip())
    compact = re.sub(r"[^\w\-一-龥]", "", compact)
    return compact or "section"


def safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", text).strip() or "interface"


def translate_label(value: Any) -> str:
    text = str(value)
    return DISPLAY_LABELS.get(text, text)


def render_scroll_box(content: str, kind: str = "default") -> RawHtml:
    return RawHtml(f'<div class="cell-scroll {html.escape(kind)}">{content}</div>')


def resolve_source_field_alias(token: str, alias_map: dict[str, str] | None = None) -> str:
    token = token.strip()
    if not token:
        return ""
    merged_aliases = dict(SOURCE_FIELD_ALIASES)
    if alias_map:
        merged_aliases.update({key: value for key, value in alias_map.items() if value})
    alias = merged_aliases.get(token, "")
    return f"{token}：{alias}" if alias else token


def source_field_pair(token: str, alias_map: dict[str, str] | None = None) -> tuple[str, str]:
    token = token.strip()
    if not token:
        return "", ""
    merged_aliases = dict(SOURCE_FIELD_ALIASES)
    if alias_map:
        merged_aliases.update({key: value for key, value in alias_map.items() if value})
    return token, merged_aliases.get(token, "")


def render_tag_list(
    values: Any,
    empty_text: str = "未提供",
    alias_map: dict[str, str] | None = None,
) -> RawHtml:
    tokens = [stringify_short(item) for item in as_list(values)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return RawHtml(f'<span class="muted">{html.escape(empty_text)}</span>')
    rows = []
    for token in tokens:
        field, label = source_field_pair(token, alias_map)
        label_html = html.escape(label) if label else '<span class="muted">未标注</span>'
        rows.append(
            '<div class="field-pair-line">'
            f'<code>{html.escape(field)}</code>'
            f'<span>{label_html}</span>'
            '</div>'
        )
    return render_scroll_box(f'<div class="field-pair-list">{"".join(rows)}</div>', "field-scroll")


def infer_table_variant(headers: list[str]) -> str:
    header_set = {str(header) for header in headers}
    if [str(header) for header in headers] == ["字段", "内容"]:
        return "key-value"
    if len(headers) >= 6 or header_set & (LONG_TEXT_HEADERS | FIELD_LIST_HEADERS | PATH_HEADERS):
        return "wide"
    return "standard"


def column_css_class(header: Any) -> str:
    label = str(header)
    if label in ACTION_HEADERS:
        return "col-action"
    if label in STATUS_HEADERS:
        return "col-status"
    if label in DB_FIELD_HEADERS:
        return "col-db-field"
    if label in FIELD_NAME_HEADERS:
        return "col-field-name"
    if label in ASSIGNMENT_TYPE_HEADERS:
        return "col-assignment-type"
    if label in VALIDATION_LEVEL_HEADERS:
        return "col-validation-level"
    if label in SOURCE_NAME_HEADERS:
        return "col-source-name"
    if label in COUNT_HEADERS:
        return "col-count"
    if label in PATH_HEADERS:
        return "col-path"
    if label in PRIMARY_FIELD_LIST_HEADERS:
        return "col-primary-field-list"
    if label in SECONDARY_FIELD_LIST_HEADERS:
        return "col-secondary-field-list"
    if label in FIELD_LIST_HEADERS:
        return "col-field-list"
    if label in LONG_TEXT_HEADERS:
        return "col-note"
    return "col-default"


def stringify_short(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [stringify_short(item) for item in value[:5]]
        parts = [part for part in parts if part]
        return "；".join(parts)
    if isinstance(value, dict):
        parts = []
        for key, child in value.items():
            text = stringify_short(child)
            if text:
                parts.append(f"{key}: {text}")
        return "；".join(parts[:5])
    return str(value)


def render_text(value: Any) -> str:
    if isinstance(value, RawHtml):
        return str(value)
    if value is None or value == "":
        return '<span class="muted">未提供</span>'
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return html.escape(str(value))
    return html.escape(str(value))


def render_cell(value: Any) -> str:
    if isinstance(value, RawHtml):
        return str(value)
    if isinstance(value, dict):
        pairs = "".join(
            f"<li><strong>{html.escape(translate_label(key))}</strong>: {render_text(child)}</li>"
            for key, child in value.items()
        )
        return f"<ul>{pairs}</ul>"
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            limited = value[:5]
            return render_table(limited)
        items = "".join(f"<li>{render_text(item)}</li>" for item in value[:10])
        return f"<ul>{items}</ul>"
    return render_text(value)


def render_table(rows: list[dict[str, Any]], preferred_headers: list[str] | None = None) -> str:
    if not rows:
        return '<p class="muted">无可展示数据</p>'

    headers: list[str] = []
    if preferred_headers:
        for key in preferred_headers:
            if any(key in row for row in rows):
                headers.append(key)
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    variant = infer_table_variant(headers)
    thead = "".join(
        f'<th class="{column_css_class(key)}">{html.escape(translate_label(key))}</th>'
        for key in headers
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            f'<td class="{column_css_class(key)}">{render_cell(row.get(key))}</td>'
            for key in headers
        )
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<div class="table-wrap">'
        f'<table class="data-table {variant}"><thead><tr>{thead}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table>"
        "</div>"
    )


def render_table_with_grouped_cells(
    rows: list[dict[str, Any]],
    preferred_headers: list[str],
    *,
    group_key: str,
    grouped_headers: list[str],
) -> str:
    if not rows:
        return '<p class="muted">无可展示数据</p>'

    headers: list[str] = []
    for key in preferred_headers:
        if any(key in row for row in rows):
            headers.append(key)
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    rowspans: dict[tuple[int, str], int] = {}
    skip_cells: set[tuple[int, str]] = set()
    index = 0
    while index < len(rows):
        group_value = str(rows[index].get(group_key, ""))
        end_index = index + 1
        while end_index < len(rows) and str(rows[end_index].get(group_key, "")) == group_value:
            end_index += 1
        span = end_index - index
        if span > 1:
            for header in grouped_headers:
                if header not in headers:
                    continue
                rowspans[(index, header)] = span
                for skip_index in range(index + 1, end_index):
                    skip_cells.add((skip_index, header))
        index = end_index

    variant = infer_table_variant(headers)
    thead = "".join(
        f'<th class="{column_css_class(key)}">{html.escape(translate_label(key))}</th>'
        for key in headers
    )
    body_rows = []
    for row_index, row in enumerate(rows):
        cells = []
        for key in headers:
            if (row_index, key) in skip_cells:
                continue
            rowspan = rowspans.get((row_index, key))
            rowspan_attr = f' rowspan="{rowspan}"' if rowspan else ""
            cells.append(
                f'<td class="{column_css_class(key)}"{rowspan_attr}>{render_cell(row.get(key))}</td>'
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="table-wrap">'
        f'<table class="data-table {variant}"><thead><tr>{thead}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table>"
        "</div>"
    )


def render_key_value(data: Any) -> str:
    if isinstance(data, dict):
        rows = [{"字段": translate_label(key), "内容": value} for key, value in data.items()]
        return render_table(rows, ["字段", "内容"])
    if isinstance(data, list):
        if not data:
            return '<p class="muted">无可展示数据</p>'
        if data and all(isinstance(item, dict) for item in data):
            return render_table(data[:20])
        items = "".join(f"<li>{render_text(item)}</li>" for item in data[:20])
        return f"<ul>{items}</ul>"
    return f"<p>{render_text(data)}</p>"


def display_table_name(table_name: str) -> str:
    label = TARGET_TABLE_ALIASES.get(table_name)
    if label:
        return f"{label}（{table_name}）"
    return table_name


def extract_target_table_from_field(value: Any) -> list[str]:
    tables: list[str] = []
    for token in as_list(value):
        text = stringify_short(token)
        if not text:
            continue
        for part in re.split(r"[/,，、\s]+", text):
            cleaned = part.strip("()（）[]【】")
            if "." not in cleaned:
                continue
            table_name = cleaned.split(".", 1)[0].strip()
            if table_name:
                tables.append(table_name)
    return tables


def infer_target_tables(data: dict[str, Any]) -> str:
    tables: list[str] = []
    for rule in as_list(data.get("field_assignment_rules")):
        if not isinstance(rule, dict):
            continue
        for key in ("target_table", "target_tables"):
            for table_name in as_list(rule.get(key)):
                text = stringify_short(table_name)
                if text:
                    tables.append(text)
        for key in ("target_field_group", "target_field", "target_fields"):
            tables.extend(extract_target_table_from_field(rule.get(key)))
    table_names = dedupe_keep_order(tables)
    if not table_names:
        return ""
    return " / ".join(display_table_name(table_name) for table_name in table_names)


def summarize_staging_layer(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value.strip()

    tables: list[str] = []

    def collect_tables(node: Any) -> None:
        if isinstance(node, dict):
            if "tables" in node:
                for table_name in as_list(node.get("tables")):
                    text = stringify_short(table_name)
                    if text:
                        tables.append(text)
            for child in node.values():
                collect_tables(child)
        elif isinstance(node, list):
            for child in node:
                collect_tables(child)

    collect_tables(value)
    table_names = dedupe_keep_order(tables)
    if table_names:
        displayed = " / ".join(display_table_name(table_name) for table_name in table_names[:5])
        return f"中间层/迁移映射层（{displayed}）"
    return "中间层/迁移映射层"


def stage_first_value(summary: dict[str, Any], items: list[dict[str, Any]], keys: list[str]) -> Any:
    for key in keys:
        value = summary.get(key)
        if value not in (None, "", [], {}):
            return value
    for item in items:
        value = first_non_empty(item, keys)
        if value not in (None, "", [], {}):
            return value
    return None


def extract_stage_count_summary(texts: list[str]) -> str:
    parts: list[str] = []
    for text in texts:
        for segment in re.split(r"[；;。]\s*", text):
            normalized = segment.strip(" ，,。；;")
            if not normalized or not re.search(r"\d", normalized):
                continue
            if re.search(r"(数|量|条|个|次|批|项|类|关系|成片|成员|映射|缺失|差异|归零|失败|成功|目标|源)", normalized):
                parts.append(normalized)
    return "；".join(dedupe_keep_order(parts)[:8])


def compact_stage_details(summary: dict[str, Any], items: list[dict[str, Any]]) -> str:
    details: list[str] = []
    for key in ("detail", "result", "summary", "conclusion", "note"):
        value = stringify_short(summary.get(key))
        if value:
            details.append(value)
    for item in items:
        for key in ("detail", "result", "summary", "conclusion", "note", "reason"):
            value = stringify_short(item.get(key))
            if value:
                details.append(value)
                break
    return "；".join(dedupe_keep_order(details))


def stage_status_summary(status: str) -> str:
    normalized = normalize_detail_status(status, "BLOCKED")
    if normalized == "PASS":
        return "该阶段核验通过。"
    if normalized == "FAIL":
        return "该阶段存在失败项，需修复后复核。"
    if normalized == "BLOCKED":
        return "该阶段存在阻塞项，需补齐阻塞条件后复核。"
    if normalized == "WARN":
        return "该阶段存在待关注项，需确认后闭环。"
    if normalized == "N/A":
        return "当前接口无该阶段可展示明细。"
    return "该阶段核验结果需结合明细确认。"


def render_stage_summary_section(data: dict[str, Any], summary_key: str, entry: dict[str, Any]) -> str:
    summary = data.get(summary_key)
    if not isinstance(summary, dict):
        return render_key_value(summary)

    items = [item for item in as_list(summary.get("items")) if isinstance(item, dict)]
    fallback_status = stringify_short(summary.get("status")) or "BLOCKED"
    if items:
        stage_status = status_from_items(items, fallback_status)
    else:
        stage_status = normalize_detail_status(fallback_status, "N/A")

    stage_detail = compact_stage_details(summary, items)
    count_summary = stringify_short(
        stage_first_value(
            summary,
            items,
            [
                "verified_count",
                "checked_count",
                "total_count",
                "source_count",
                "target_count",
                "relation_count",
                "expected_count",
                "核验总条数",
                "核验总量",
            ],
        )
    ) or extract_stage_count_summary([stage_detail])

    source_value = stage_first_value(
        summary,
        items,
        ["verification_source", "data_source", "source", "source_table", "source_api", "核验数据源"],
    )
    target_value = stage_first_value(
        summary,
        items,
        ["target_object", "target_table", "target_tables", "target", "目标对象", "目标表"],
    )
    staging_value = stage_first_value(
        summary,
        items,
        ["staging_layer", "staging_object", "mapping_layer", "middle_layer", "中间层", "映射层"],
    ) or data.get("staging_layer")

    entry_name = stringify_short(entry.get("display_name") or entry.get("name"))
    entry_path = stringify_short(entry.get("path"))
    source_interface = f"{entry_name}（{entry_path}）" if entry_name and entry_path else entry_name or entry_path

    if summary_key == "source_to_staging_summary":
        data_source = stringify_short(source_value) or source_interface or "源接口/源数据"
        target_object = stringify_short(target_value) or summarize_staging_layer(staging_value) or "中间层/迁移映射层"
    else:
        data_source = stringify_short(source_value) or summarize_staging_layer(staging_value) or "中间层/迁移映射层"
        target_object = stringify_short(target_value) or infer_target_tables(data) or stringify_short(target_source_value(data)) or "目标业务表"

    rows = [
        {"字段": "核验数据源", "内容": data_source},
        {"字段": "目标对象", "内容": target_object},
        {"字段": "核验总条数", "内容": count_summary or "未提供"},
        {"字段": "阶段状态", "内容": stage_status},
    ]
    return render_table(rows, ["字段", "内容"])


def field_display_name(field_name: str, aliases: dict[str, str]) -> str:
    field_name = field_name.strip()
    if not field_name:
        return ""
    base_name = field_name.rsplit(".", 1)[-1]
    label = aliases.get(field_name) or aliases.get(base_name)
    if label:
        technical_name = field_name if aliases is SOURCE_FIELD_ALIASES and "." in field_name else base_name
        return f"{label}（{technical_name}）"
    return field_name


def field_label(field_name: str, aliases: dict[str, str]) -> str:
    field_name = field_name.strip()
    if not field_name:
        return ""
    base_name = field_name.rsplit(".", 1)[-1]
    return aliases.get(field_name) or aliases.get(base_name) or field_name


def target_field_label(rule: dict[str, Any], full_field: str, column: str) -> str:
    meaning = rule.get("field_meaning") or rule.get("target_field_meaning") or rule.get("field_comment")
    if isinstance(meaning, dict):
        for key in (full_field, column):
            value = stringify_short(meaning.get(key))
            if value:
                return value
    text = stringify_short(meaning)
    if text:
        return text
    return field_label(full_field, TARGET_FIELD_ALIASES)


def field_match_key(field_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", field_name.lower())


def source_field_matches_hint(source_field: str, hint: str) -> bool:
    source_key = field_match_key(source_field)
    source_base_key = field_match_key(source_field.rsplit(".", 1)[-1])
    if hint == "resplist":
        return source_key.startswith("resplist") or source_key.startswith("commentlistresplist")
    return source_key == hint or source_base_key == hint


def source_fields_for_target(target_field: str, source_fields: Any) -> list[str]:
    tokens = [stringify_short(item) for item in as_list(source_fields)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return []

    base_name = target_field.rsplit(".", 1)[-1]
    hints = TARGET_SOURCE_FIELD_HINTS.get(target_field) or TARGET_SOURCE_FIELD_HINTS.get(base_name)
    if not hints:
        return tokens

    selected: list[str] = []
    for source_field in tokens:
        if any(source_field_matches_hint(source_field, hint) for hint in hints):
            selected.append(source_field)
    return selected or tokens


def target_source_specs(rule: dict[str, Any], target_field: str, fallback_source_fields: Any) -> list[dict[str, Any]]:
    base_name = target_field.rsplit(".", 1)[-1]
    source_map = rule.get("target_field_sources")
    explicit = None
    if isinstance(source_map, dict):
        explicit = source_map.get(target_field) or source_map.get(base_name)

    if explicit is None:
        return [
            {
                "scenario": "通用",
                "source_fields": source_fields_for_target(target_field, fallback_source_fields),
            }
        ]

    specs: list[dict[str, Any]] = []
    for item in as_list(explicit):
        if isinstance(item, dict):
            fields = item.get("source_fields") or item.get("fields") or item.get("source_field")
            scenario = item.get("scenario") or item.get("scope") or "通用"
        else:
            fields = item
            scenario = "通用"
        specs.append(
            {
                "scenario": scenario,
                "source_fields": [stringify_short(field) for field in as_list(fields) if stringify_short(field)],
            }
        )
    return specs or [{"scenario": "通用", "source_fields": []}]


def render_field_chip_list(values: Any, aliases: dict[str, str], empty_text: str = "未提供") -> RawHtml:
    tokens = [stringify_short(item) for item in as_list(values)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return RawHtml(f'<span class="muted">{html.escape(empty_text)}</span>')
    chips = "".join(
        f'<span class="chip">{html.escape(field_display_name(token, aliases))}</span>'
        for token in tokens
    )
    return render_scroll_box(f'<div class="chip-list">{chips}</div>', "field-scroll")


def render_plain_field_list(values: Any, aliases: dict[str, str], empty_text: str = "未提供") -> RawHtml:
    tokens = [stringify_short(item) for item in as_list(values)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return RawHtml(f'<span class="muted">{html.escape(empty_text)}</span>')
    lines = "".join(
        f'<div class="plain-field-line">{html.escape(field_display_name(token, aliases))}</div>'
        for token in tokens
    )
    return render_scroll_box(f'<div class="plain-field-list">{lines}</div>', "field-scroll")


def infer_default_target_table(data: dict[str, Any]) -> str:
    target_sources = data.get("target_sources")
    tables = target_sources.get("tables") if isinstance(target_sources, dict) else []
    table_names = [str(item) for item in as_list(tables) if str(item)]
    if "view_media_annotation" in table_names:
        return "view_media_annotation"
    business_tables = [
        name
        for name in table_names
        if not name.startswith("view_migration_") and name not in {"user"}
    ]
    return business_tables[0] if business_tables else "未标明目标表"


def split_target_field(field_name: str, default_table: str) -> tuple[str, str]:
    field_name = field_name.strip()
    if "." in field_name:
        table_name, column_name = field_name.rsplit(".", 1)
        return table_name, column_name
    return default_table, field_name


def fallback_split_field_group(value: Any) -> list[str]:
    text = stringify_short(value)
    if not text:
        return []
    parts = re.split(r"[；;,，/]+", text)
    return [part.strip() for part in parts if part.strip()]


def grouped_target_fields(rule: dict[str, Any], default_table: str) -> dict[str, list[str]]:
    raw_fields = [stringify_short(item) for item in as_list(rule.get("target_fields"))]
    raw_fields = [item for item in raw_fields if item]
    if not raw_fields:
        raw_fields = fallback_split_field_group(rule.get("target_field_group") or rule.get("target_field"))

    grouped: dict[str, list[str]] = {}
    for raw_field in raw_fields:
        table_name, column_name = split_target_field(raw_field, default_table)
        grouped.setdefault(table_name, [])
        if column_name not in grouped[table_name]:
            grouped[table_name].append(column_name)
    return grouped


def is_business_target_table(table_name: str) -> bool:
    return (
        bool(table_name)
        and table_name != "未标明目标表"
        and not table_name.startswith("view_migration_")
        and table_name not in {"user"}
    )


def render_source_fields_text(values: Any) -> str:
    tokens = [stringify_short(item) for item in as_list(values)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return "未提供"
    return "、".join(field_display_name(token, SOURCE_FIELD_ALIASES) for token in tokens)


def field_specific_rule_lines(rule: dict[str, Any], full_field: str, keys: tuple[str, ...]) -> list[str]:
    table_name, column_name = split_target_field(full_field, "")
    for key in keys:
        value = rule.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            value = value.get(full_field) or value.get(column_name) or value.get("default")
        lines = [stringify_short(item) for item in as_list(value)]
        lines = [line for line in lines if line]
        if lines:
            return lines
    return []


def field_assignment_explanation(rule: dict[str, Any], full_field: str, specs: list[dict[str, Any]]) -> list[str]:
    table_name, column_name = split_target_field(full_field, "")
    spec_map = {
        stringify_short(spec.get("scenario")) or "通用": render_source_fields_text(spec.get("source_fields"))
        for spec in specs
    }

    if table_name == "view_media_annotation" and column_name == "id":
        return [
            f"主批注：取 {spec_map.get('主批注', 'videoId、commentList.id')} 组成旧业务键 videoId:commentId。",
            f"回复：取 {spec_map.get('回复', 'videoId、commentList.respList.id')} 组成旧业务键 videoId:reply:replyId。",
            "写入目标：用旧业务键命中 MEDIA_AUDIT_COMMENT_MATERIAL 映射记录，取映射表 new_id 写入目标 id。",
        ]
    if table_name == "view_media_annotation" and column_name == "media_id":
        return [
            f"主批注：取 {spec_map.get('主批注', 'videoId、commentList.version')}，按 videoId:version 查 MEDIA_VERSION_MATERIAL 映射，命中后写入目标 media_id。",
            f"回复：取 {spec_map.get('回复', '父批注.media_id')}，直接继承父批注的 media_id。",
            "兜底：版本映射缺失时回退到 MEDIA_MATERIAL.new_id，并在核验中标记风险。",
        ]
    if table_name == "view_media_annotation" and column_name == "content":
        return [
            f"主批注：将 {spec_map.get('主批注', 'content')} 原样写入 content。",
            f"回复：将 {spec_map.get('回复', 'respList.content')} 原样写入 content。",
        ]
    if table_name == "view_media_annotation" and column_name == "start_timestamp_ms":
        return [f"取 {spec_map.get('主批注', 'startTime')} 的中文时间文本，转换为毫秒后写入 start_timestamp_ms。"]
    if table_name == "view_media_annotation" and column_name == "end_timestamp_ms":
        return [f"取 {spec_map.get('主批注', 'endTime')} 的中文时间文本，转换为毫秒后写入 end_timestamp_ms。"]
    if table_name == "view_media_annotation" and column_name == "annotation_type":
        return [
            f"取 {spec_map.get('主批注', 'startTime、endTime')} 比较开始和结束时间。",
            "startTime 等于 endTime 时写入 SINGLE；不相等时写入 RANGE。",
        ]
    if table_name == "view_media_annotation" and column_name == "create_by_name":
        return [
            f"主批注：取 {spec_map.get('主批注', 'accountName')} 写入批注人名称。",
            f"回复：取 {spec_map.get('回复', 'respList.accountName')} 写入批注人名称。",
        ]
    if table_name == "view_media_annotation" and column_name == "create_by_user_id":
        return [
            f"主批注：用 {spec_map.get('主批注', 'accountName')} 在目标用户表反查用户 ID。",
            f"回复：用 {spec_map.get('回复', 'respList.accountName')} 在目标用户表反查用户 ID。",
            "写入目标：反查命中的用户 ID 写入 create_by_user_id。",
        ]
    if table_name == "view_media_annotation" and column_name == "mention_user_ids":
        return [
            f"主批注：用 {spec_map.get('主批注', 'receiveAccountName')} 在目标用户表反查 @ 人员 ID。",
            f"回复：用 {spec_map.get('回复', 'respList.receiveAccountName')} 在目标用户表反查 @ 人员 ID。",
            "源为空时目标保持为空。",
        ]
    if table_name == "view_media_annotation" and column_name == "parent_id":
        return [f"仅回复记录使用：取 {spec_map.get('回复', 'commentList.id')} 对应的父批注目标 id，写入 parent_id。"]
    if table_name == "view_media_annotation" and column_name == "reply_to_id":
        return [f"仅回复记录使用：取 {spec_map.get('回复', 'commentList.id')} 对应的被回复批注目标 id，写入 reply_to_id。"]
    if table_name == "view_media_annotation" and column_name == "reply_to_name":
        return [f"仅回复记录使用：取 {spec_map.get('回复', 'respList.respAccountName')} 写入 reply_to_name。"]
    if table_name == "view_media_annotation" and column_name == "status":
        return ["源 commentList 没有完成态字段；迁移时按默认规则写入 COMPLETED。"]

    lines: list[str] = []
    for spec in specs:
        scenario = stringify_short(spec.get("scenario")) or "通用"
        lines.append(f"{scenario}：来源 {render_source_fields_text(spec.get('source_fields'))}")
    rule_text = stringify_short(rule.get("rule_expression"))
    if rule_text:
        lines.append(f"规则：{rule_text}")
    return lines


def render_assignment_rule_value(rule: dict[str, Any], full_field: str, source_fields: Any) -> RawHtml:
    expected_lines = field_specific_rule_lines(
        rule,
        full_field,
        ("expected_assignment_rule", "expected_assignment_rules", "expected_rule"),
    )
    actual_lines = field_specific_rule_lines(
        rule,
        full_field,
        ("actual_validation_rule", "actual_validation_rules", "actual_rule"),
    )
    basis_lines = field_specific_rule_lines(rule, full_field, ("rule_basis", "rule_basis_note"))
    consistency_lines = field_specific_rule_lines(
        rule,
        full_field,
        ("rule_consistency_status", "rule_consistency_note"),
    )
    if expected_lines or actual_lines or basis_lines or consistency_lines:
        lines: list[str] = []
        for line in expected_lines:
            lines.append(f"预期赋值规则：{line}")
        for line in actual_lines:
            lines.append(f"实际核验规则：{line}")
        for line in basis_lines:
            lines.append(f"规则依据：{line}")
        for line in consistency_lines:
            lines.append(f"规则说明：{line}")
        html_lines = "".join(f'<div class="plain-field-line">{html.escape(line)}</div>' for line in lines)
        return render_scroll_box(f'<div class="plain-field-list">{html_lines}</div>', "field-scroll")

    specs = target_source_specs(rule, full_field, source_fields)
    lines = field_assignment_explanation(rule, full_field, specs)
    if not lines:
        lines.append("未提供赋值规则")
    html_lines = "".join(f'<div class="plain-field-line">{html.escape(line)}</div>' for line in lines)
    return render_scroll_box(f'<div class="plain-field-list">{html_lines}</div>', "field-scroll")


def render_rule_part_value(
    lines: list[str],
    *,
    empty_text: str = "未提供",
    prefix: str = "",
) -> RawHtml:
    if not lines:
        return RawHtml(f'<span class="muted">{html.escape(empty_text)}</span>')
    html_lines = "".join(
        f'<div class="plain-field-line">{html.escape(prefix + line if prefix else line)}</div>'
        for line in lines
    )
    return render_scroll_box(f'<div class="plain-field-list">{html_lines}</div>', "field-scroll")


def split_assignment_rule_columns(rule: dict[str, Any], full_field: str, source_fields: Any) -> tuple[RawHtml, RawHtml]:
    expected_lines = field_specific_rule_lines(
        rule,
        full_field,
        ("expected_assignment_rule", "expected_assignment_rules", "expected_rule"),
    )
    actual_lines = field_specific_rule_lines(
        rule,
        full_field,
        ("actual_validation_rule", "actual_validation_rules", "actual_rule"),
    )
    if not expected_lines and not actual_lines:
        specs = target_source_specs(rule, full_field, source_fields)
        expected_lines = field_assignment_explanation(rule, full_field, specs)

    return (
        render_rule_part_value(expected_lines),
        render_rule_part_value(actual_lines, empty_text="同预期规则或未单独提供"),
    )


def accuracy_target_matches_field(target_text: str, full_field: str) -> bool:
    target_text = stringify_short(target_text)
    if not target_text:
        return False
    table_name, column_name = split_target_field(full_field, "")
    if full_field and full_field in target_text:
        return True
    if table_name and target_text.startswith(f"{table_name}."):
        tail = target_text[len(table_name) + 1 :]
        tokens = [token.strip() for token in re.split(r"[/,，；; ]+", tail) if token.strip()]
        return column_name in tokens
    return False


def accuracy_for_field(full_field: str, accuracy_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    exact_matches: list[dict[str, Any]] = []
    grouped_matches: list[dict[str, Any]] = []
    for item in accuracy_items:
        target_text = stringify_short(item.get("target_field"))
        if target_text == full_field:
            exact_matches.append(item)
        elif accuracy_target_matches_field(target_text, full_field):
            grouped_matches.append(item)
    candidates = exact_matches or grouped_matches
    if not candidates:
        return None
    status_priority = {"FAIL": 0, "BLOCKED": 1, "WARN": 2, "PASS": 3, "N/A": 4}
    return sorted(candidates, key=lambda item: status_priority.get(str(item.get("status")), 9))[0]


def sample_matches_field(sample: dict[str, Any], full_field: str) -> bool:
    field_text = " ".join(
        stringify_short(sample.get(key))
        for key in ("difference_field", "target_field", "field_name")
        if sample.get(key) is not None
    )
    if not field_text:
        return False
    table_name, column_name = split_target_field(full_field, "")
    return full_field in field_text or column_name in re.split(r"[/,，；; ]+", field_text)


def format_difference_sample(sample: dict[str, Any]) -> str:
    parts: list[str] = []
    business_key = stringify_short(sample.get("business_key"))
    if business_key:
        parts.append(f"业务键={business_key}")
    source_value = stringify_short(sample.get("source_value"))
    target_value = stringify_short(sample.get("target_value"))
    if source_value or target_value:
        parts.append(f"源值={source_value or '空'}，目标值={target_value or '空'}")
    note = stringify_short(sample.get("difference_note"))
    if note:
        parts.append(note)
    return "；".join(parts) or stringify_short(sample)


def render_difference_note_for_field(
    accuracy_item: dict[str, Any] | None,
    samples: list[dict[str, Any]],
) -> RawHtml | str:
    if accuracy_item is None:
        return "未提供核验结果"

    mismatched = parse_int(accuracy_item.get("mismatched_count"))
    if mismatched <= 0:
        note = stringify_short(accuracy_item.get("difference_note"))
        if note and note != "无差异":
            return RawHtml(
                '<div class="plain-field-list">'
                f'<div class="plain-field-line">{html.escape(note)}</div>'
                "</div>"
            )
        return "无差异"

    lines: list[str] = []
    note = stringify_short(accuracy_item.get("difference_note"))
    if note:
        lines.append(note)
    for index, sample in enumerate(samples[:3], start=1):
        lines.append(f"{index}. {format_difference_sample(sample)}")
    if not lines:
        lines.append("存在差异，未提供结构化样例")
    html_lines = "".join(f'<div class="plain-field-line">{html.escape(line)}</div>' for line in lines)
    return render_scroll_box(f'<div class="plain-field-list">{html_lines}</div>', "field-scroll")


def collect_difference_samples_for_field(data: dict[str, Any], full_field: str, contract: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    groups = ["field_differences", "relationship_differences", "file_differences"]
    if contract:
        groups = list(contract.get("difference_groups") or groups)
    samples: list[dict[str, Any]] = []
    for group_name in groups:
        for sample in collect_samples(data.get(group_name), {"difference_field", "target_field", "field_name"}):
            if isinstance(sample, dict) and sample_matches_field(sample, full_field):
                samples.append(sample)
    return samples


def render_database_assignment_and_accuracy_section(data: dict[str, Any], contract: dict[str, Any] | None = None) -> str:
    rules = [item for item in as_list(data.get("field_assignment_rules")) if isinstance(item, dict)]
    if not rules:
        return '<p class="muted">无可展示数据</p>'

    default_table = infer_default_target_table(data)
    table_rows: dict[str, list[dict[str, Any]]] = {}
    seen_fields: set[tuple[str, str]] = set()
    accuracy_items = [
        item
        for item in as_list(data.get("field_accuracy_details") or data.get("field_accuracy_summary"))
        if isinstance(item, dict)
    ]
    for rule in rules:
        grouped_fields = grouped_target_fields(rule, default_table)
        if not grouped_fields:
            continue
        source_fields = rule.get("source_fields") or fallback_split_field_group(rule.get("source_field_group"))
        for table_name, columns in grouped_fields.items():
            if not is_business_target_table(table_name):
                continue
            target_fields = columns or ["未标明目标字段"]
            for column in target_fields:
                field_key = (table_name, column)
                if field_key in seen_fields:
                    continue
                seen_fields.add(field_key)
                full_field = f"{table_name}.{column}"
                accuracy_item = accuracy_for_field(full_field, accuracy_items)
                samples = collect_difference_samples_for_field(data, full_field, contract)
                expected_rule, actual_rule = split_assignment_rule_columns(rule, full_field, source_fields)
                table_rows.setdefault(table_name, []).append(
                    {
                        "表字段": column,
                        "字段名": target_field_label(rule, full_field, column),
                        "赋值方式": rule.get("assignment_type"),
                        "预期赋值规则": expected_rule,
                        "实际核验规则": actual_rule,
                        "核验级别": accuracy_item.get("validation_level") if accuracy_item else "未提供",
                        "检查记录数": accuracy_item.get("checked_count") if accuracy_item else "未提供",
                        "不匹配记录数": accuracy_item.get("mismatched_count") if accuracy_item else "未提供",
                        "状态": accuracy_item.get("status") if accuracy_item else "未提供",
                        "差异说明": render_difference_note_for_field(accuracy_item, samples),
                    }
                )

    headers = [
        "表字段",
        "字段名",
        "赋值方式",
        "预期赋值规则",
        "实际核验规则",
        "核验级别",
        "检查记录数",
        "不匹配记录数",
        "状态",
        "差异说明",
    ]
    parts = [
        '<p class="section-note">本章节只展示目标业务表字段，不展示迁移映射表；每个目标数据库字段一行，并拆开展示预期赋值规则、实际核验规则和字段核验结果。规则依据缺失、待确认或不适用时，合并写入状态与差异说明；普通通过字段且无不匹配记录时显示“无差异”。</p>'
    ]
    for index, (table_name, rows) in enumerate(table_rows.items(), start=1):
        parts.append('<div class="rule-group">')
        parts.append(f"<h3>表{index}：{html.escape(display_table_name(table_name))}</h3>")
        parts.append(render_table(rows, headers))
        parts.append("</div>")
    return "".join(parts) if table_rows else '<p class="muted">无业务目标表字段可展示</p>'


def render_database_assignment_rules_section(data: dict[str, Any]) -> str:
    return render_database_assignment_and_accuracy_section(data)


def collect_samples(node: Any, required_keys: set[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if required_keys & node.keys():
            items.append(node)
        for value in node.values():
            items.extend(collect_samples(value, required_keys))
    elif isinstance(node, list):
        for value in node:
            items.extend(collect_samples(value, required_keys))
    return items


def count_fields(data: dict[str, Any]) -> dict[str, int]:
    rules = as_list(data.get("field_assignment_rules"))
    details = as_list(data.get("field_accuracy_details"))
    summary = as_list(data.get("field_accuracy_summary"))
    accuracy_source = details or summary

    target_fields = {
        str(item.get("target_field"))
        for item in accuracy_source
        if isinstance(item, dict) and item.get("target_field")
    }
    if not target_fields:
        target_fields = {
            str(item.get("target_field_group"))
            for item in rules
            if isinstance(item, dict) and item.get("target_field_group")
        }

    statuses = Counter(
        str(item.get("status"))
        for item in accuracy_source
        if isinstance(item, dict) and item.get("status")
    )

    return {
        "critical_field_total": len(target_fields),
        "fields_with_rules": len(rules),
        "fields_validated": len(accuracy_source),
        "fail_fields": statuses.get("FAIL", 0),
        "blocked_fields": statuses.get("BLOCKED", 0),
        "na_fields": statuses.get("N/A", 0),
    }


def main_report_status(status: Any) -> str:
    normalized = stringify_short(status).upper()
    if normalized in MAIN_REPORT_STATUSES:
        return normalized
    return "PASS"


def main_overall_status(data: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    entry_statuses = [main_report_status(entry.get("status")) for entry in entries]
    if "FAIL" in entry_statuses:
        return "FAIL"
    if "BLOCKED" in entry_statuses:
        return "BLOCKED"
    return main_report_status(get_status(data))


def summary_cards(
    data: dict[str, Any],
    entries: list[dict[str, Any]],
    counts: dict[str, int],
    *,
    main: bool = False,
) -> list[dict[str, str]]:
    if main:
        status_counts = Counter(main_report_status(entry.get("status")) for entry in entries)
        return [
            {"label": "总体结论", "value": main_overall_status(data, entries)},
            {"label": "测试接口数", "value": str(max(len(entries), 1))},
            {"label": "通过接口数", "value": str(status_counts.get("PASS", 0))},
            {"label": "阻塞接口数", "value": str(status_counts.get("BLOCKED", 0))},
            {"label": "失败接口数", "value": str(status_counts.get("FAIL", 0))},
        ]
    return [
        {"label": "总体结论", "value": get_status(data)},
        {"label": "接口数", "value": str(max(len(entries), 1))},
        {"label": "关键字段", "value": str(counts["critical_field_total"])},
        {"label": "已核验字段", "value": str(counts["fields_validated"])},
        {"label": "FAIL 字段", "value": str(counts["fail_fields"])},
        {"label": "BLOCKED 字段", "value": str(counts["blocked_fields"])},
    ]


def normalize_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(normalize_strings(item))
        return items
    if isinstance(value, dict):
        text = stringify_short(value)
        return [text] if text else []
    text = str(value).strip()
    return [text] if text else []


def scope_matches(scope: Any, interface_name: str) -> bool:
    if isinstance(scope, str):
        return interface_name == scope or interface_name in scope
    if isinstance(scope, list):
        return any(scope_matches(item, interface_name) for item in scope)
    return False


def matches_interface(item: Any, interface_name: str, contract: dict[str, Any]) -> bool:
    if interface_name == DEFAULT_INTERFACE_NAME:
        return True
    if not isinstance(item, dict):
        return False
    identity = get_identity(item, contract["interface_identity_keys"])
    if identity == interface_name:
        return True
    for key in ("impact_scope", "interface_scope", "affected_interface", "affected_interfaces", "interfaces"):
        if scope_matches(item.get(key), interface_name):
            return True
    return False


def filter_items_by_interface(
    items: Any,
    interface_name: str,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    filtered = []
    for item in as_list(items):
        if not isinstance(item, dict):
            continue
        if matches_interface(item, interface_name, contract):
            filtered.append(item)
    return filtered


def normalize_detail_status(status: Any, fallback: str = "BLOCKED") -> str:
    normalized = stringify_short(status).upper()
    if normalized in {"FAIL", "BLOCKED", "WARN", "PASS", "N/A"}:
        return normalized
    return fallback


def status_from_items(items: list[dict[str, Any]], fallback: str = "BLOCKED") -> str:
    statuses = [
        normalize_detail_status(item.get("status"))
        for item in items
        if isinstance(item, dict) and item.get("status") not in (None, "")
    ]
    for status in ("FAIL", "BLOCKED", "WARN", "PASS", "N/A"):
        if status in statuses:
            return status
    return normalize_detail_status(fallback)


def filter_summary_by_interface(value: Any, interface_name: str, contract: dict[str, Any]) -> Any:
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        return value
    filtered_items = filter_items_by_interface(value.get("items"), interface_name, contract)
    fallback_status = stringify_short(value.get("status")) or "BLOCKED"
    if not filtered_items:
        fallback_status = "N/A"
    return {
        **value,
        "status": status_from_items(filtered_items, fallback_status),
        "items": filtered_items,
    }


def build_interface_conclusion(entry: dict[str, Any]) -> dict[str, Any]:
    summary = stringify_short(entry.get("summary"))
    reasons = [stringify_short(reason) for reason in as_list(entry.get("reasons")) if stringify_short(reason)]
    conclusion: dict[str, Any] = {"status": entry.get("status") or "BLOCKED"}
    if summary:
        conclusion["summary"] = summary
    if reasons:
        conclusion["reason"] = "；".join(dedupe_keep_order(reasons)[:3])
    elif summary:
        conclusion["reason"] = summary
    return conclusion


def interface_detail_title(entry: dict[str, Any]) -> str:
    display_name = stringify_short(entry.get("display_name") or entry.get("name")) or DEFAULT_INTERFACE_NAME
    return f"{display_name} 核验明细报告"


def build_inventory_map(data: dict[str, Any], contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    inventory_map: dict[str, dict[str, Any]] = {}
    for item in as_list(data.get("interface_inventory")):
        if not isinstance(item, dict):
            continue
        name = get_identity(item, contract["interface_identity_keys"])
        if name:
            inventory_map[name] = item
    return inventory_map


def build_inventory_path_map(data: dict[str, Any], contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    inventory_map: dict[str, dict[str, Any]] = {}
    for item in as_list(data.get("interface_inventory")):
        if not isinstance(item, dict):
            continue
        path = stringify_short(first_non_empty(item, contract["interface_path_keys"]))
        if path:
            inventory_map[path] = item
    return inventory_map


def build_source_field_alias_map(data: dict[str, Any]) -> dict[str, str]:
    alias_map = dict(SOURCE_FIELD_ALIASES)
    for item in as_list(data.get("field_assignment_rules")):
        if not isinstance(item, dict):
            continue
        source_field = stringify_short(item.get("source_fields"))
        field_meaning = stringify_short(item.get("field_meaning"))
        if not source_field or not field_meaning:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source_field):
            continue
        alias_map.setdefault(source_field, field_meaning)
    return alias_map


def extract_interface_path(item: Any, contract: dict[str, Any]) -> str:
    value = first_non_empty(item, contract["interface_path_keys"])
    if value in (None, "", [], {}):
        value = first_non_empty(item, contract["interface_identity_keys"])
    return stringify_short(value) or "未提供"


def resolve_source_interface_display_name(
    item: dict[str, Any],
    contract: dict[str, Any],
    inventory_map: dict[str, dict[str, Any]],
    inventory_path_map: dict[str, dict[str, Any]],
) -> str:
    explicit_name = stringify_short(
        first_non_empty(
            item,
            [
                "source_interface_name",
                "source_api_name",
                "display_name",
                "business_domain",
                "interface_title",
                "title",
                "api_title",
            ],
        )
    )
    if explicit_name:
        return explicit_name

    interface_name = stringify_short(item.get("interface_name"))
    interface_path = stringify_short(item.get("interface_path"))

    inventory_item = {}
    if interface_name and interface_name in inventory_map:
        inventory_item = inventory_map[interface_name]
    elif interface_path and interface_path in inventory_path_map:
        inventory_item = inventory_path_map[interface_path]

    inventory_name = stringify_short(
        first_non_empty(
            inventory_item,
            [
                "source_interface_name",
                "source_api_name",
                "display_name",
                "business_domain",
                "interface_title",
                "title",
                "api_title",
            ],
        )
    )
    if inventory_name:
        return inventory_name

    if interface_name and interface_name != interface_path:
        return interface_name
    return interface_path or interface_name or "未提供"


def collect_interface_causes(value: Any, interface_name: str, contract: dict[str, Any]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        if interface_name != DEFAULT_INTERFACE_NAME and interface_name in value:
            return normalize_strings(value[interface_name])
        if matches_interface(value, interface_name, contract):
            texts = []
            explicit = first_non_empty(value, contract["interface_reason_keys"])
            if explicit:
                texts.extend(normalize_strings(explicit))
            if not texts:
                texts.extend(normalize_strings(value))
            return texts
        if interface_name == DEFAULT_INTERFACE_NAME:
            return normalize_strings(value)
        return []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                if matches_interface(item, interface_name, contract):
                    explicit = first_non_empty(item, contract["interface_reason_keys"])
                    if explicit:
                        texts.extend(normalize_strings(explicit))
                    else:
                        texts.extend(normalize_strings(item))
                elif interface_name == DEFAULT_INTERFACE_NAME:
                    texts.extend(normalize_strings(item))
            elif interface_name == DEFAULT_INTERFACE_NAME:
                texts.extend(normalize_strings(item))
        return texts
    if interface_name == DEFAULT_INTERFACE_NAME:
        return normalize_strings(value)
    return []


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def build_interface_entry(
    interface_name: str,
    data: dict[str, Any],
    contract: dict[str, Any],
    inventory_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    inventory_item = inventory_map.get(interface_name, {})
    rule_items = filter_items_by_interface(data.get("field_assignment_rules"), interface_name, contract)
    accuracy_items = filter_items_by_interface(
        data.get("field_accuracy_details") or data.get("field_accuracy_summary"),
        interface_name,
        contract,
    )
    coverage_items = filter_items_by_interface(data.get("coverage_gaps"), interface_name, contract)

    sample_keys = set(contract["input"]["difference_sample_required_keys"])
    sample_items: list[dict[str, Any]] = []
    for group_name in contract["difference_groups"]:
        for item in collect_samples(data.get(group_name), sample_keys):
            if matches_interface(item, interface_name, contract):
                sample_copy = dict(item)
                sample_copy["group"] = group_name
                sample_items.append(sample_copy)

    status_counter = Counter(
        str(item.get("status"))
        for item in accuracy_items
        if isinstance(item, dict) and item.get("status")
    )
    coverage_status_counter = Counter(
        str(item.get("status"))
        for item in coverage_items
        if isinstance(item, dict) and item.get("status")
    )

    explicit_status = stringify_short(first_non_empty(inventory_item, ["status", "result", "conclusion"]))
    if explicit_status:
        status = explicit_status
    elif status_counter.get("FAIL", 0):
        status = "FAIL"
    elif coverage_status_counter.get("BLOCKED", 0) or status_counter.get("BLOCKED", 0):
        status = "BLOCKED"
    elif status_counter.get("WARN", 0) or coverage_status_counter.get("WARN", 0) or sample_items:
        status = "WARN"
    elif accuracy_items or rule_items:
        status = "PASS"
    else:
        status = get_status(data)

    path = extract_interface_path(inventory_item, contract)
    explicit_summary = stringify_short(first_non_empty(inventory_item, contract["interface_summary_keys"]))
    summary_parts = []
    if explicit_summary:
        summary_parts.append(explicit_summary)
    if status_counter.get("FAIL", 0):
        summary_parts.append(f"字段核验 FAIL {status_counter['FAIL']} 项")
    if status_counter.get("BLOCKED", 0):
        summary_parts.append(f"字段核验 BLOCKED {status_counter['BLOCKED']} 项")
    if coverage_status_counter.get("BLOCKED", 0):
        summary_parts.append(f"覆盖阻塞 {coverage_status_counter['BLOCKED']} 项")
    if sample_items:
        summary_parts.append(f"差异样例 {len(sample_items)} 条")
    if not summary_parts:
        summary_parts.append("未提供接口级概述，详见分接口明细页")

    reasons = []
    reasons.extend(collect_interface_causes(data.get("likely_causes"), interface_name, contract))
    reasons.extend(collect_interface_causes(data.get("blocked_items"), interface_name, contract))
    for item in coverage_items:
        reason_text = stringify_short(first_non_empty(item, ["reason", "gap_item", "note"]))
        if reason_text:
            reasons.append(reason_text)
    if status_counter.get("FAIL", 0):
        reasons.append(f"字段核验存在 {status_counter['FAIL']} 个 FAIL 项")
    if coverage_status_counter.get("BLOCKED", 0):
        reasons.append(f"覆盖缺口存在 {coverage_status_counter['BLOCKED']} 个 BLOCKED 项")
    if sample_items:
        reasons.append(f"已识别 {len(sample_items)} 条代表差异样例")

    display_name = stringify_short(
        first_non_empty(inventory_item, ["display_name", "business_domain", "interface_title", "title"])
    ) or interface_name

    return {
        "name": interface_name,
        "display_name": display_name,
        "status": status,
        "path": path,
        "summary": "；".join(dedupe_keep_order(summary_parts)),
        "fail_fields": status_counter.get("FAIL", 0),
        "blocked_fields": status_counter.get("BLOCKED", 0) + coverage_status_counter.get("BLOCKED", 0),
        "warn_fields": status_counter.get("WARN", 0),
        "difference_count": len(sample_items),
        "coverage_gap_count": len(coverage_items),
        "rule_items": rule_items,
        "accuracy_items": accuracy_items,
        "coverage_items": coverage_items,
        "sample_items": sample_items,
        "reasons": dedupe_keep_order(reasons),
        "inventory_item": inventory_item,
    }


def build_interface_entries(data: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    inventory_map = build_inventory_map(data, contract)
    names = infer_interface_names(data, contract)
    all_names = sorted(set(names) | set(inventory_map.keys()))
    effective_names = all_names or [DEFAULT_INTERFACE_NAME]
    return [build_interface_entry(name, data, contract, inventory_map) for name in effective_names]


def relative_link(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, start=from_path.parent)).as_posix()


def build_interface_links(
    entries: list[dict[str, Any]],
    output_html: Path,
    interface_dir: Path | None,
) -> dict[str, str]:
    if not interface_dir:
        return {}
    links = {}
    for entry in entries:
        target = interface_dir / f"{safe_filename(entry['name'])}.html"
        links[entry["name"]] = relative_link(output_html, target)
    return links


def render_interface_block(title: str, status: str, bullets: list[str]) -> str:
    items = "".join(f"<li>{render_text(item)}</li>" for item in bullets if item)
    return (
        '<div class="interface-block">'
        f'<h3>{html.escape(title)} <span class="status {html.escape(status)}">{html.escape(status)}</span></h3>'
        f"<ul>{items}</ul>"
        "</div>"
    )


def render_summary_section(data: dict[str, Any], entries: list[dict[str, Any]], counts: dict[str, int]) -> str:
    conclusion = data.get("conclusion", {})
    reason = ""
    if isinstance(conclusion, dict):
        reason = stringify_short(conclusion.get("reason") or conclusion.get("summary"))
    blocked_items = as_list(data.get("blocked_items"))
    parts = [
        f'<p><span class="status {html.escape(get_status(data))}">{html.escape(get_status(data))}</span></p>',
        f"<p>{render_text(reason) if reason else '本报告基于已提供的核验结果生成，结论以结构化证据为准。'}</p>",
        (
            "<p>"
            f"识别接口数量: {len(entries)}，关键字段总数: {counts['critical_field_total']}，"
            f"已完成字段核验: {counts['fields_validated']}，FAIL 字段: {counts['fail_fields']}。"
            "</p>"
        ),
    ]
    if blocked_items:
        parts.append("<h3>当前阻塞项</h3>")
        parts.append(render_key_value(blocked_items[:10]))
    return "".join(parts)


def render_status_badge(status: str) -> RawHtml:
    normalized = html.escape(status)
    return RawHtml(f'<span class="status {normalized}">{normalized}</span>')


def compact_main_text(value: Any, fallback: str = "未提供", max_length: int = 180) -> str:
    text = " ".join(stringify_short(value).split())
    if not text:
        return fallback
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def first_nested_non_empty(container: Any, keys: list[str]) -> Any:
    if not isinstance(container, dict):
        return None
    return first_non_empty(container, keys)


def resolve_main_context(
    data: dict[str, Any],
    entry: dict[str, Any],
    inventory_keys: list[str],
    top_level_keys: list[str],
    nested_sources: list[tuple[str, list[str]]],
    *,
    max_length: int = 180,
) -> str:
    inventory_item = entry.get("inventory_item", {})
    value = first_non_empty(inventory_item, inventory_keys)
    for source_key, keys in nested_sources:
        if value not in (None, "", [], {}):
            break
        value = first_nested_non_empty(data.get(source_key), keys)
    if value in (None, "", [], {}):
        value = first_non_empty(data, top_level_keys)
    return compact_main_text(value, max_length=max_length)


def entry_scope_summary(data: dict[str, Any], entry: dict[str, Any]) -> str:
    return resolve_main_context(
        data,
        entry,
        ["verification_scope", "scope", "data_scope", "batch_scope", "migration_scope"],
        ["verification_scope", "batch_scope"],
        [("verification_scope", ["summary", "batch_scope", "object_counts", "time_filter_rule"])],
    )


def entry_rule_summary(data: dict[str, Any], entry: dict[str, Any]) -> str:
    return resolve_main_context(
        data,
        entry,
        ["verification_rule", "validation_rule", "check_rule", "rule", "migration_rule"],
        ["verification_rule", "validation_rule", "business_keys", "full_chain_consistency_summary"],
        [("verification_scope", ["verification_rule", "validation_rule", "rule", "time_filter_rule"])],
    )


def entry_environment_summary(data: dict[str, Any], entry: dict[str, Any]) -> str:
    return resolve_main_context(
        data,
        entry,
        ["verification_environment", "environment", "env", "environment_scope"],
        ["environment", "env", "target_sources"],
        [
            ("verification_scope", ["environment_scope", "environment", "env"]),
            ("target_sources", ["environment", "env", "database", "database_alias"]),
        ],
        max_length=120,
    )


def render_execution_overview(data: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    status_counts = Counter(main_report_status(entry.get("status")) for entry in entries)
    rows = [
        {
            "总体结论": render_status_badge(main_overall_status(data, entries)),
            "测试接口数": max(len(entries), 1),
            "通过接口数": status_counts.get("PASS", 0),
            "阻塞接口数": status_counts.get("BLOCKED", 0),
            "失败接口数": status_counts.get("FAIL", 0),
        }
    ]
    conclusion = data.get("conclusion", {})
    reason = ""
    if isinstance(conclusion, dict):
        reason = stringify_short(conclusion.get("reason") or conclusion.get("summary"))
    if not reason:
        reason = "本报告基于已提供的核验结果生成，结论以结构化证据为准。"
    return render_table(rows, ["总体结论", "测试接口数", "通过接口数", "阻塞接口数", "失败接口数"]) + f"<p>{render_text(reason)}</p>"


def summarize_count_map(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "未提供"
    return "；".join(f"{key}={stringify_short(item)}" for key, item in value.items())


def parse_job_param(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("job_param")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_batch_rows(batch_rows: Any) -> str:
    rows = [row for row in as_list(batch_rows) if isinstance(row, dict)]
    if not rows:
        return "未提供批次记录"

    statuses = Counter(stringify_short(row.get("status")) or "UNKNOWN" for row in rows)
    stages = sorted({stringify_short(row.get("stage")) for row in rows if stringify_short(row.get("stage"))})
    total_count = sum(int(row.get("total_count") or 0) for row in rows)
    success_count = sum(int(row.get("success_count") or 0) for row in rows)
    failed_count = sum(int(row.get("failed_count") or 0) for row in rows)
    job_params = [parse_job_param(row) for row in rows]
    content_codes = sorted({stringify_short(item.get("contentCode")) for item in job_params if stringify_short(item.get("contentCode"))})
    upload_starts = [stringify_short(item.get("uploadStartTime")) for item in job_params if stringify_short(item.get("uploadStartTime"))]
    upload_ends = [stringify_short(item.get("uploadEndTime")) for item in job_params if stringify_short(item.get("uploadEndTime"))]
    start_times = [stringify_short(row.get("start_time")) for row in rows if stringify_short(row.get("start_time"))]
    end_times = [stringify_short(row.get("end_time")) for row in rows if stringify_short(row.get("end_time"))]

    parts = [
        f"批次记录 {len(rows)} 条",
        f"状态：{summarize_count_map(dict(statuses))}",
        f"阶段：{', '.join(stages) if stages else '未提供'}",
        f"total/success/failed={total_count}/{success_count}/{failed_count}",
    ]
    if content_codes:
        parts.append(f"contentCode={', '.join(content_codes)}")
    if upload_starts or upload_ends:
        parts.append(f"上传时间范围={min(upload_starts) if upload_starts else '未提供'}~{max(upload_ends) if upload_ends else '未提供'}")
    if start_times:
        parts.append(f"执行窗口={min(start_times)}~{max(end_times) if end_times else '存在未结束批次'}")
    return "；".join(parts)


def render_source_and_target_section(data: dict[str, Any]) -> str:
    staging = data.get("staging_layer") if isinstance(data.get("staging_layer"), dict) else {}
    target = data.get("target_sources") if isinstance(data.get("target_sources"), dict) else {}

    rows = [
        {
            "来源层级": "中间层",
            "来源对象": "view_migration_batch",
            "摘要": summarize_batch_rows(staging.get("batch_rows")),
            "明细位置": "结构化 JSON 的 staging_layer.batch_rows",
        },
        {
            "来源层级": "中间层",
            "来源对象": "view_migration_id_map",
            "摘要": summarize_count_map(staging.get("mapping_summary")),
            "明细位置": "结构化 JSON 的 staging_layer.mapping_summary",
        },
    ]
    if isinstance(staging.get("comment_mapping_type_counts"), dict):
        rows.append(
            {
                "来源层级": "中间层",
                "来源对象": "批注专项映射类型",
                "摘要": summarize_count_map(staging.get("comment_mapping_type_counts")),
                "明细位置": "结构化 JSON 的 staging_layer.comment_mapping_type_counts",
            }
        )
    if staging.get("live_request_batches_sample") is not None:
        rows.append(
            {
                "来源层级": "源接口回查",
                "来源对象": "live 请求批次样例",
                "摘要": "主报告不展开请求批次明细；源接口请求总量、失败数和缺失素材数见“源基准来源”。",
                "明细位置": "结构化 JSON 的 staging_layer.live_request_batches_sample",
            }
        )

    rows.append(
        {
            "来源层级": "目标层",
            "来源对象": stringify_short(target.get("database_alias")) or "目标数据库",
            "摘要": f"数据库={stringify_short(target.get('database')) or '未提供'}；涉及表={stringify_short(target.get('tables')) or '未提供'}",
            "明细位置": "结构化 JSON 的 target_sources",
        }
    )
    return render_table(rows, ["来源层级", "来源对象", "摘要", "明细位置"])


def render_source_field_coverage_section(data: dict[str, Any], contract: dict[str, Any]) -> str:
    summary = data.get("field_rule_coverage_summary") or {}
    inventory_map = build_inventory_map(data, contract)
    inventory_path_map = build_inventory_path_map(data, contract)
    alias_map = build_source_field_alias_map(data)
    inventory_rows = []
    for item in as_list(data.get("source_field_inventory")):
        if not isinstance(item, dict):
            continue
        inventory_rows.append(
            {
                "源接口名称": resolve_source_interface_display_name(item, contract, inventory_map, inventory_path_map),
                "接口路径": item.get("interface_path"),
                "源字段总数": len(as_list(item.get("actual_source_fields"))),
                "文档预期字段": render_tag_list(item.get("documented_expected_fields"), alias_map=alias_map),
                "实际响应独有字段": render_tag_list(item.get("live_actual_only_fields"), alias_map=alias_map),
                "中间层独有字段": render_tag_list(item.get("staging_snapshot_only_fields"), alias_map=alias_map),
                "已纳入规则字段": render_tag_list(item.get("mapped_fields"), alias_map=alias_map),
                "N/A 字段": render_tag_list(item.get("na_fields"), alias_map=alias_map),
                "未采集字段": render_tag_list(item.get("explicitly_uncollected_fields"), alias_map=alias_map),
                "未纳入规则字段": render_tag_list(item.get("unmapped_fields"), alias_map=alias_map),
                "说明": item.get("note"),
            }
        )

    content = [
        render_key_value(summary),
        render_table(
            inventory_rows,
            [
                "源接口名称",
                "接口路径",
                "源字段总数",
                "文档预期字段",
                "实际响应独有字段",
                "中间层独有字段",
                "已纳入规则字段",
                "N/A 字段",
                "未采集字段",
                "未纳入规则字段",
                "说明",
            ],
        ),
    ]

    unmapped_rows = []
    for item in as_list(data.get("unmapped_source_fields")):
        if not isinstance(item, dict):
            continue
        unmapped_rows.append(
            {
                "源接口名称": resolve_source_interface_display_name(item, contract, inventory_map, inventory_path_map),
                "字段名": item.get("field_name"),
                "当前状态": item.get("current_status"),
                "原因": item.get("reason"),
                "建议动作": item.get("suggested_action"),
            }
        )
    if unmapped_rows:
        content.append("<h3>未纳入规则字段</h3>")
        content.append(render_table(unmapped_rows, ["源接口名称", "字段名", "当前状态", "原因", "建议动作"]))
    return "".join(content)


def render_interface_source_inventory_section(data: dict[str, Any], interface_name: str, contract: dict[str, Any]) -> str:
    inventory_items = filter_items_by_interface(data.get("source_field_inventory"), interface_name, contract)
    if not inventory_items:
        return '<p class="muted">当前接口未提供源字段盘点。</p>'

    inventory_map = build_inventory_map(data, contract)
    inventory_path_map = build_inventory_path_map(data, contract)
    alias_map = build_source_field_alias_map(data)
    rows = []
    for item in inventory_items:
        rows.append(
            {
                "源接口名称": resolve_source_interface_display_name(item, contract, inventory_map, inventory_path_map),
                "接口路径": item.get("interface_path"),
                "实际源字段": render_tag_list(item.get("actual_source_fields"), alias_map=alias_map),
                "文档预期字段": render_tag_list(item.get("documented_expected_fields"), alias_map=alias_map),
                "实际响应独有字段": render_tag_list(item.get("live_actual_only_fields"), alias_map=alias_map),
                "中间层独有字段": render_tag_list(item.get("staging_snapshot_only_fields"), alias_map=alias_map),
                "已纳入规则字段": render_tag_list(item.get("mapped_fields"), alias_map=alias_map),
                "N/A 字段": render_tag_list(item.get("na_fields"), alias_map=alias_map),
                "未采集字段": render_tag_list(item.get("explicitly_uncollected_fields"), alias_map=alias_map),
                "未纳入规则字段": render_tag_list(item.get("unmapped_fields"), alias_map=alias_map),
                "说明": item.get("note"),
            }
        )

    unmapped_rows = filter_items_by_interface(data.get("unmapped_source_fields"), interface_name, contract)
    html_parts = [
        render_table(
            rows,
            [
                "源接口名称",
                "接口路径",
                "实际源字段",
                "文档预期字段",
                "实际响应独有字段",
                "中间层独有字段",
                "已纳入规则字段",
                "N/A 字段",
                "未采集字段",
                "未纳入规则字段",
                "说明",
            ],
        )
    ]
    if unmapped_rows:
        html_parts.append("<h3>当前接口未纳入规则字段</h3>")
        normalized_unmapped_rows = []
        for item in unmapped_rows:
            normalized_unmapped_rows.append(
                {
                    "源接口名称": resolve_source_interface_display_name(item, contract, inventory_map, inventory_path_map),
                    "字段名": item.get("field_name"),
                    "当前状态": item.get("current_status"),
                    "原因": item.get("reason"),
                    "建议动作": item.get("suggested_action"),
                }
            )
        html_parts.append(render_table(normalized_unmapped_rows, ["源接口名称", "字段名", "当前状态", "原因", "建议动作"]))
    return "".join(html_parts)


def render_results_overview(entries: list[dict[str, Any]]) -> str:
    blocks = []
    for entry in entries:
        summary_parts = [entry["summary"]]
        statistic_parts = []
        status = main_report_status(entry["status"])
        if entry["fail_fields"]:
            statistic_parts.append(f"失败字段 {entry['fail_fields']} 项")
        if entry["blocked_fields"]:
            statistic_parts.append(f"阻塞字段 {entry['blocked_fields']} 项")
        if entry["difference_count"]:
            statistic_parts.append(f"差异样例 {entry['difference_count']} 条")
        if entry["coverage_gap_count"]:
            statistic_parts.append(f"覆盖或证据缺口 {entry['coverage_gap_count']} 项")
        if statistic_parts:
            summary_parts.append("，".join(statistic_parts))
        for reason in entry["reasons"][:3]:
            summary_parts.append(f"关键问题：{reason}")
        result_summary = "；".join(dedupe_keep_order(summary_parts))
        blocks.append(
            (
                '<div class="interface-block conclusion-block">'
                '<div class="conclusion-grid">'
                '<div class="conclusion-item">'
                '<div class="conclusion-label">接口名称</div>'
                f'<div class="conclusion-value">{render_text(entry["display_name"])}</div>'
                "</div>"
                '<div class="conclusion-item">'
                '<div class="conclusion-label">核验接口路径</div>'
                f'<div class="conclusion-value">{render_text(entry["path"])}</div>'
                "</div>"
                '<div class="conclusion-item conclusion-summary">'
                '<div class="conclusion-label">核验结果概述</div>'
                f'<div class="conclusion-value">{render_status_badge(status)} {render_text(result_summary)}</div>'
                "</div>"
                "</div>"
                "</div>"
            )
        )
    return "".join(blocks)


def render_detail_index(
    data: dict[str, Any],
    entries: list[dict[str, Any]],
    interface_links: dict[str, str],
) -> str:
    rows = []
    for entry in entries:
        href = interface_links.get(entry["name"])
        link_html = RawHtml(
            f'<a class="detail-link" href="{html.escape(href)}" title="查看 {html.escape(entry["display_name"])} 明细">查看详情</a>'
        ) if href else RawHtml('<span class="muted">未生成明细页</span>')
        rows.append(
            {
                "接口名称": entry["display_name"],
                "接口路径": entry["path"],
                "核验范围": entry_scope_summary(data, entry),
                "核验规则": entry_rule_summary(data, entry),
                "核验环境": entry_environment_summary(data, entry),
                "核验状态": render_status_badge(main_report_status(entry["status"])),
                "查看明细": link_html,
            }
        )
    return render_table(rows, ["接口名称", "接口路径", "核验范围", "核验规则", "核验环境", "核验状态", "查看明细"])


def render_failure_summary(entries: list[dict[str, Any]]) -> str:
    entries = [entry for entry in entries if entry["status"] in {"FAIL", "WARN", "BLOCKED"}]
    if not entries:
        return '<p class="muted">当前无失败、阻塞或告警项。</p>'
    blocks = []
    for entry in entries:
        bullets = entry["reasons"][:]
        if not bullets:
            bullets = ["未提供接口级原因，当前仅保留结论摘要。"]
        blocks.append(render_interface_block(entry["display_name"], entry["status"], bullets))
    return "".join(blocks)


def render_difference_samples(samples: list[dict[str, Any]], contract: dict[str, Any]) -> str:
    rows = []
    for item in samples[:20]:
        row = {key: item.get(key) for key in contract["input"]["difference_sample_required_keys"]}
        row["group"] = item.get("group")
        rows.append(row)
    return render_table(rows, ["group", *contract["input"]["difference_sample_required_keys"]])


def render_conclusion_section(data: dict[str, Any], counts: dict[str, int]) -> str:
    conclusion = data.get("conclusion", {})
    items = [
        {"字段": "总体状态", "内容": get_status(data)},
        {"字段": "关键字段总数", "内容": counts["critical_field_total"]},
        {"字段": "已有规则基线字段数", "内容": counts["fields_with_rules"]},
        {"字段": "已完成准确性核验字段数", "内容": counts["fields_validated"]},
        {"字段": "FAIL 字段数", "内容": counts["fail_fields"]},
        {"字段": "BLOCKED 字段数", "内容": counts["blocked_fields"]},
        {"字段": "N/A 字段数", "内容": counts["na_fields"]},
    ]
    if isinstance(conclusion, dict):
        for key in ("reason", "summary", "next_action"):
            if key in conclusion:
                items.append({"字段": translate_label(key), "内容": conclusion.get(key)})
    return render_table(items, ["字段", "内容"])


def render_section(
    section: str,
    data: dict[str, Any],
    contract: dict[str, Any],
    entries: list[dict[str, Any]],
    counts: dict[str, int],
    interface_links: dict[str, str],
) -> str:
    if section == "执行结果概述":
        return render_execution_overview(data, entries)
    if section == "执行摘要":
        return render_summary_section(data, entries, counts)
    if section == "核验范围与口径":
        return render_key_value(data.get("verification_scope"))
    if section == "核验时间证据":
        return render_key_value(data.get("time_evidence"))
    if section == "源基准来源":
        return render_key_value(data.get("source_baseline"))
    if section == "源接口字段覆盖自检":
        return render_source_field_coverage_section(data, contract)
    if section == "中间层来源与目标来源":
        return render_source_and_target_section(data)
    if section == "核验结论概述":
        return render_results_overview(entries)
    if section == "核验结果概述":
        return render_results_overview(entries)
    if section == "核验明细":
        return render_detail_index(data, entries, interface_links)
    if section == "失败原因总结":
        return render_failure_summary(entries)
    return '<p class="muted">未配置该章节的渲染逻辑。</p>'


def fill_template(
    template: str,
    *,
    title: str,
    subtitle: str,
    cards: list[dict[str, str]],
    sections: list[tuple[str, str]],
    toc_mode: str = "top",
) -> str:
    summary_cards_html = "".join(
        (
            '<div class="summary-card">'
            f'<div class="label">{html.escape(card["label"])}</div>'
            f'<div class="value">{html.escape(card["value"])}</div>'
            "</div>"
        )
        for card in cards
    )

    toc_html = "<ul>" + "".join(
        f'<li><a href="#{slugify(title_text)}">{html.escape(title_text)}</a></li>'
        for title_text, _ in sections
    ) + "</ul>"

    sections_html = "".join(
        f'<section class="panel" id="{slugify(title_text)}"><h2>{html.escape(title_text)}</h2>{body}</section>'
        for title_text, body in sections
    )
    if toc_mode == "none":
        body_content = sections_html
    elif toc_mode == "side":
        body_content = (
            '<div class="detail-layout">'
            f'<aside class="toc side-toc"><h2>目录</h2>{toc_html}</aside>'
            f'<main class="detail-content">{sections_html}</main>'
            "</div>"
        )
    else:
        body_content = f'<section class="toc"><h2>目录</h2>{toc_html}</section>{sections_html}'

    return (
        template.replace("{{title}}", html.escape(title))
        .replace("{{subtitle}}", html.escape(subtitle))
        .replace("{{summary_cards}}", summary_cards_html)
        .replace("{{body_content}}", body_content)
    )


def interface_view(
    data: dict[str, Any],
    interface_name: str,
    contract: dict[str, Any],
    entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if interface_name == DEFAULT_INTERFACE_NAME:
        return dict(data)

    cloned = dict(data)
    for key in ("interface_inventory", "field_assignment_rules", "field_accuracy_summary", "field_accuracy_details", "coverage_gaps"):
        cloned[key] = filter_items_by_interface(data.get(key), interface_name, contract)

    for key in contract["difference_groups"]:
        cloned[key] = filter_items_by_interface(data.get(key), interface_name, contract)

    for key in (
        "source_to_staging_summary",
        "staging_to_target_summary",
        "full_chain_consistency_summary",
        "uniqueness_summary",
        "totals_summary",
        "source_fields_not_persisted",
    ):
        cloned[key] = filter_summary_by_interface(data.get(key), interface_name, contract)

    if entry:
        cloned["conclusion"] = build_interface_conclusion(entry)

    return cloned


def resolve_delivery_mode(requested_mode: str, is_multi: bool) -> tuple[str, list[str]]:
    notes: list[str] = []
    if requested_mode == "draft":
        return "draft", notes
    if is_multi:
        if requested_mode == "standard":
            notes.append("识别到多个接口，已按约束升级为 full，输出主报告和分接口明细页。")
        return "full", notes
    if requested_mode == "full":
        notes.append("识别到单接口，已按约束降级为 standard，直接输出明细报告。")
    return "standard", notes


def target_source_value(data: dict[str, Any]) -> Any:
    return data.get("target_sources") if "target_sources" in data else data.get("target_source")


def render_direct_chain_result_section(data: dict[str, Any]) -> str:
    rows = [
        {"字段": "源基线证据", "内容": data.get("source_baseline")},
        {"字段": "目标来源证据", "内容": target_source_value(data)},
        {"字段": "业务键与匹配策略", "内容": data.get("business_keys")},
        {"字段": "源到目标核验结果", "内容": data.get("totals_summary")},
    ]
    return render_table(rows, ["字段", "内容"])


def render_direct_integrity_section(data: dict[str, Any]) -> str:
    rows = [
        {"字段": "完整性统计", "内容": data.get("totals_summary")},
        {"字段": "唯一性统计", "内容": data.get("uniqueness_summary")},
        {"字段": "源有目标无", "内容": data.get("missing_in_target")},
        {"字段": "目标有源无", "内容": data.get("extra_in_target")},
        {"字段": "目标重复", "内容": data.get("duplicate_in_target")},
        {"字段": "源重复", "内容": data.get("duplicate_in_source")},
    ]
    return render_table(rows, ["字段", "内容"])


def render_source_fields_not_persisted_section(data: dict[str, Any]) -> str:
    value = data.get("source_fields_not_persisted")
    if value in (None, "", [], {}):
        return '<p class="muted">无可展示数据</p>'
    return render_key_value(value)


def build_interface_page_sections(
    page_data: dict[str, Any],
    entry: dict[str, Any],
    contract: dict[str, Any],
    chain_type: str,
) -> list[tuple[str, str]]:
    page_counts = count_fields(page_data)
    common_sections = [
        (
            "接口概况",
            render_interface_block(
                entry["display_name"],
                entry["status"],
                [
                    f"接口路径：{entry['path']}",
                    f"核验概述：{entry['summary']}",
                ],
            ),
        ),
        ("源接口字段盘点与归类", render_interface_source_inventory_section(page_data, entry["name"], contract)),
        ("目标数据库赋值规则及核验结果", render_database_assignment_and_accuracy_section(page_data, contract)),
    ]
    if chain_type == "direct":
        return [
            *common_sections,
            ("源到目标核验结果", render_direct_chain_result_section(page_data)),
            ("完整性与唯一性核验结果", render_direct_integrity_section(page_data)),
            ("接口字段未入库说明", render_source_fields_not_persisted_section(page_data)),
            ("覆盖缺口与不适用说明", render_key_value(page_data.get("coverage_gaps"))),
            ("差异样例", render_difference_samples(entry["sample_items"], contract)),
            ("接口结论", render_conclusion_section(page_data, page_counts)),
        ]
    return [
        *common_sections,
        ("覆盖缺口与不适用说明", render_key_value(page_data.get("coverage_gaps"))),
        ("源到中间层核验结果", render_stage_summary_section(page_data, "source_to_staging_summary", entry)),
        ("中间层到目标核验结果", render_stage_summary_section(page_data, "staging_to_target_summary", entry)),
        ("差异样例", render_difference_samples(entry["sample_items"], contract)),
        ("接口结论", render_conclusion_section(page_data, page_counts)),
    ]


def write_json_output(
    output_json: Path,
    data: dict[str, Any],
    mode: str,
    chain_type: str,
    entries: list[dict[str, Any]],
    counts: dict[str, int],
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["_report_meta"] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "delivery_mode": mode,
        "chain_type": chain_type,
        "interface_names": [entry["name"] for entry in entries],
        "counts": counts,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="渲染 API 迁移核验报告 HTML。")
    parser.add_argument("--input", required=True, help="结构化输入 JSON 路径")
    parser.add_argument("--output-html", help="主报告或单接口明细 HTML 输出路径")
    parser.add_argument("--output-json", required=True, help="结构化 JSON 输出路径")
    parser.add_argument("--interface-dir", help="分接口 HTML 输出目录")
    parser.add_argument(
        "--mode",
        choices=("auto", "draft", "standard", "full"),
        default="auto",
        help="交付模式",
    )
    parser.add_argument(
        "--chain-type",
        choices=("auto", "direct", "staged"),
        default="auto",
        help="迁移链路类型；auto 会按输入字段推断",
    )
    parser.add_argument("--title", help="报告标题")
    parser.add_argument("--contract", type=Path, default=None, help="contract JSON 路径")
    parser.add_argument("--template", type=Path, default=None, help="HTML 模板路径")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    contract = load_json(args.contract or default_contract_path())
    template = (args.template or default_template_path()).read_text(encoding="utf-8")
    input_path = Path(args.input)
    data = load_json(input_path)
    chain_type = infer_chain_type(data, contract, args.chain_type)
    entries = build_interface_entries(data, contract)
    is_multi = len(entries) > 1
    mode, mode_notes = resolve_delivery_mode(args.mode, is_multi)

    counts = count_fields(data)
    write_json_output(Path(args.output_json), data, mode, chain_type, entries, counts)
    for note in mode_notes:
        print(f"WARNING: {note}")

    if mode == "draft":
        print(f"Generated JSON only: {args.output_json}")
        return 0

    if not args.output_html:
        parser.error("正式 HTML 模式必须提供 --output-html")

    mode_policy = contract["delivery_modes"][mode]
    output_html = Path(args.output_html)
    interface_dir = Path(args.interface_dir) if args.interface_dir else None
    if mode_policy["requires_interface_pages"] and interface_dir is None:
        parser.error(f"{mode} 模式必须提供 --interface-dir")

    title = args.title or data.get("task_meta", {}).get("task_name") or input_path.stem
    subtitle = f"链路类型: {chain_type} | 交付模式: {mode} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    output_html.parent.mkdir(parents=True, exist_ok=True)

    if not mode_policy["requires_main_html"]:
        entry = entries[0]
        page_data = interface_view(data, entry["name"], contract, entry)
        page_counts = count_fields(page_data)
        page_sections = build_interface_page_sections(page_data, entry, contract, chain_type)
        page_html = fill_template(
            template,
            title=interface_detail_title(entry),
            subtitle=f"链路类型: {chain_type} | 单接口明细报告 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            cards=summary_cards(page_data, [entry], page_counts),
            sections=page_sections,
            toc_mode="side",
        )
        output_html.write_text(page_html, encoding="utf-8")
        print(f"Generated detail HTML: {output_html}")
        return 0

    interface_links = build_interface_links(entries, output_html, interface_dir)
    main_sections = [
        (
            section,
            render_section(section, data, contract, entries, counts, interface_links),
        )
        for section in contract["output"]["main_sections_multi"]
    ]
    html_text = fill_template(
        template,
        title=title,
        subtitle=subtitle,
        cards=summary_cards(data, entries, counts, main=True),
        sections=main_sections,
        toc_mode="none",
    )
    output_html.write_text(html_text, encoding="utf-8")
    print(f"Generated main HTML: {output_html}")

    if mode_policy["requires_interface_pages"] and interface_dir is not None:
        interface_dir.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            page_data = interface_view(data, entry["name"], contract, entry)
            page_counts = count_fields(page_data)
            page_sections = build_interface_page_sections(page_data, entry, contract, chain_type)
            page_html = fill_template(
                template,
                title=interface_detail_title(entry),
                subtitle=f"链路类型: {chain_type} | 分接口明细页 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                cards=summary_cards(page_data, [entry], page_counts),
                sections=page_sections,
                toc_mode="side",
            )
            output_path = interface_dir / f"{safe_filename(entry['name'])}.html"
            output_path.write_text(page_html, encoding="utf-8")
            print(f"Generated interface HTML: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
