#!/usr/bin/env python3
"""
Generate a JSON-to-table mapping draft from API field comments and table column comments/names.

The script produces a reviewable mapping config. It does not verify data and does not execute writes.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")
CHINESE_RE = re.compile(r"[一-鿿]")
WORD_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")

FIELD_HEADERS = {
    "field",
    "fields",
    "name",
    "key",
    "path",
    "jsonpath",
    "json路径",
    "字段",
    "字段名",
    "参数",
    "参数名",
    "属性",
    "属性名",
}
COMMENT_HEADERS = {
    "comment",
    "comments",
    "description",
    "desc",
    "remark",
    "remarks",
    "note",
    "notes",
    "说明",
    "描述",
    "备注",
    "注释",
    "含义",
    "字段说明",
}
TYPE_HEADERS = {"type", "datatype", "data_type", "类型", "字段类型", "数据类型"}
REQUIRED_HEADERS = {"required", "must", "nullable", "必填", "是否必填", "是否必须", "是否为空", "非空"}

TECHNICAL_COLUMNS = {
    "id",
    "pk",
    "order_id",
    "created_by",
    "create_by",
    "updated_by",
    "update_by",
    "deleted",
    "is_deleted",
    "version",
}


@dataclass
class ApiField:
    json_path: str
    name: str
    comment: str = ""
    data_type: str = ""
    required: Optional[bool] = None
    source: str = ""


@dataclass
class TableColumn:
    table: str
    column_name: str
    column_comment: str = ""
    data_type: str = ""
    is_nullable: str = ""
    numeric_scale: Optional[int] = None
    column_default: Any = None
    ordinal_position: int = 0
    column_key: str = ""


@dataclass
class Candidate:
    column: TableColumn
    api_field: Optional[ApiField]
    score: float
    confidence: str
    reasons: List[str] = field(default_factory=list)


class MappingError(Exception):
    pass


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_doc(path: str) -> Any:
    ext = Path(path).suffix.lower()
    if ext in {".json"}:
        return load_json(path)
    if ext in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise MappingError("YAML document requires: pip install pyyaml") from exc
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def normalize_header(value: str) -> str:
    return re.sub(r"[\s_\-：:（）()\[\]/.]", "", str(value).strip().lower())


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("　", " ").strip().lower()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"[_\-/|:：,，.。;；()（）\[\]{}<>《》\"'`~!！?？\s]+", "", text)
    return text


def split_tokens(value: Any) -> set:
    text = "" if value is None else str(value)
    text = CAMEL_RE.sub("_", text)
    text = text.replace("_", " ").replace("-", " ").replace(".", " ")
    return {m.group(0).lower() for m in WORD_RE.finditer(text) if m.group(0).strip()}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def safe_json_path(raw: str) -> str:
    value = str(raw).strip()
    value = value.replace("[]", "[*]")
    if not value:
        return "$"
    if value.startswith("$"):
        return value
    value = value.lstrip(".")
    return "$." + value


def field_name_from_path(path: str) -> str:
    clean = path.replace("[*]", "").replace("[]", "")
    if "." in clean:
        return clean.rsplit(".", 1)[-1]
    return clean.strip("$")


def is_required(value: Any) -> Optional[bool]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "required", "must", "是", "必填", "必须", "非空", "no-null", "not null"}:
        return True
    if text in {"false", "no", "n", "0", "optional", "否", "非必填", "可空", "允许为空", "nullable"}:
        return False
    return None


def infer_mapping_type(data_type: str) -> str:
    text = (data_type or "").lower()
    if any(x in text for x in ["decimal", "numeric", "number", "float", "double", "money"]):
        return "decimal"
    if any(x in text for x in ["bigint", "int", "integer", "smallint", "tinyint", "long"]):
        return "int"
    if any(x in text for x in ["datetime", "timestamp", "time"]):
        return "datetime"
    if "date" in text:
        return "date"
    if any(x in text for x in ["bool", "bit"]):
        return "bool"
    if any(x in text for x in ["json", "object", "array"]):
        return "json"
    return "string"


def type_compatible(api_type: str, column_type: str) -> bool:
    api_norm = infer_mapping_type(api_type)
    col_norm = infer_mapping_type(column_type)
    if not api_type:
        return True
    if api_norm == col_norm:
        return True
    if col_norm == "string":
        return True
    if api_norm == "int" and col_norm == "decimal":
        return True
    return False


def parse_markdown_tables(text: str) -> List[ApiField]:
    lines = text.splitlines()
    fields: List[ApiField] = []
    i = 0
    while i < len(lines) - 1:
        header_line = lines[i].strip()
        sep_line = lines[i + 1].strip()
        if not (header_line.startswith("|") and sep_line.startswith("|")):
            i += 1
            continue
        headers = [cell.strip() for cell in header_line.strip("|").split("|")]
        seps = [cell.strip() for cell in sep_line.strip("|").split("|")]
        if len(headers) < 2 or len(headers) != len(seps) or not all(re.match(r"^:?-{2,}:?$", sep) for sep in seps):
            i += 1
            continue

        header_map = {normalize_header(h): idx for idx, h in enumerate(headers)}
        field_idx = find_header_index(header_map, FIELD_HEADERS)
        comment_idx = find_header_index(header_map, COMMENT_HEADERS)
        type_idx = find_header_index(header_map, TYPE_HEADERS)
        required_idx = find_header_index(header_map, REQUIRED_HEADERS)
        if field_idx is None:
            i += 1
            continue

        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = [cell.strip() for cell in lines[j].strip().strip("|").split("|")]
            if len(cells) < len(headers):
                cells += [""] * (len(headers) - len(cells))
            raw_name = cells[field_idx]
            if raw_name and not re.match(r"^-+$", raw_name):
                json_path = safe_json_path(raw_name)
                comment = cells[comment_idx] if comment_idx is not None and comment_idx < len(cells) else ""
                data_type = cells[type_idx] if type_idx is not None and type_idx < len(cells) else ""
                required = is_required(cells[required_idx]) if required_idx is not None and required_idx < len(cells) else None
                fields.append(ApiField(json_path=json_path, name=field_name_from_path(json_path), comment=comment, data_type=data_type, required=required, source="markdown_table"))
            j += 1
        i = j
    return dedupe_fields(fields)


def find_header_index(header_map: Dict[str, int], aliases: set) -> Optional[int]:
    normalized_aliases = {normalize_header(alias) for alias in aliases}
    for header, idx in header_map.items():
        if header in normalized_aliases:
            return idx
    for header, idx in header_map.items():
        if any(alias in header for alias in normalized_aliases):
            return idx
    return None


def parse_text_fields(text: str) -> List[ApiField]:
    fields = parse_markdown_tables(text)
    seen = {f.json_path for f in fields}
    line_re = re.compile(
        r"(?P<name>\$?\.?[A-Za-z_][A-Za-z0-9_.\[\]*-]*)\s*(?:[:：\-]|=>|->)\s*(?P<comment>[一-鿿A-Za-z0-9_（）()，,。.\s]{2,})"
    )
    for line in text.splitlines():
        match = line_re.search(line.strip())
        if not match:
            continue
        json_path = safe_json_path(match.group("name"))
        if json_path in seen:
            continue
        comment = match.group("comment").strip()
        fields.append(ApiField(json_path=json_path, name=field_name_from_path(json_path), comment=comment, source="text_line"))
        seen.add(json_path)
    return dedupe_fields(fields)


def deref(ref: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    current: Any = doc
    for part in ref[2:].split("/"):
        current = current.get(part, {}) if isinstance(current, dict) else {}
    return current if isinstance(current, dict) else {}


def merge_schema(schema: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
    if "$ref" not in schema:
        return schema
    resolved = copy.deepcopy(deref(schema["$ref"], doc))
    for key, value in schema.items():
        if key != "$ref":
            resolved[key] = value
    return resolved


def walk_schema(schema: Dict[str, Any], doc: Dict[str, Any], path: str, fields: List[ApiField], parent_required: set, source: str, seen_refs: set) -> None:
    schema = merge_schema(schema, doc)
    schema_type = schema.get("type")
    if not schema_type:
        if "properties" in schema:
            schema_type = "object"
        elif "items" in schema:
            schema_type = "array"

    if schema_type == "array":
        items = schema.get("items", {})
        walk_schema(items if isinstance(items, dict) else {}, doc, path + "[*]", fields, set(), source, seen_refs)
        return

    if schema_type == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        props = schema.get("properties", {})
        for name, prop in props.items():
            if not isinstance(prop, dict):
                continue
            prop = merge_schema(prop, doc)
            prop_path = f"{path}.{name}" if path != "$" else f"$.{name}"
            prop_type = prop.get("type", "")
            if prop_type in {"object", "array"} or "properties" in prop or "items" in prop:
                walk_schema(prop, doc, prop_path, fields, required, source, seen_refs)
            else:
                comment = first_non_empty(prop.get("description"), prop.get("title"), prop.get("x-comment"), prop.get("x-description"))
                fields.append(ApiField(json_path=prop_path, name=name, comment=comment, data_type=prop_type or prop.get("format", ""), required=name in required, source=source))
        return

    comment = first_non_empty(schema.get("description"), schema.get("title"), schema.get("x-comment"), schema.get("x-description"))
    fields.append(ApiField(json_path=path, name=field_name_from_path(path), comment=comment, data_type=schema_type or schema.get("format", ""), required=None, source=source))


def first_non_empty(*values: Any) -> str:
    for value in values:
        if value:
            return str(value).strip()
    return ""


def parse_openapi(doc: Dict[str, Any], schema_name: str = "") -> List[ApiField]:
    fields: List[ApiField] = []
    schemas = doc.get("components", {}).get("schemas", {}) or doc.get("definitions", {})
    if schema_name:
        schema = schemas.get(schema_name)
        if not schema:
            raise MappingError(f"Schema not found in API document: {schema_name}")
        walk_schema(schema, doc, "$", fields, set(), f"schema:{schema_name}", set())
    else:
        for name, schema in schemas.items():
            if isinstance(schema, dict):
                walk_schema(schema, doc, "$", fields, set(), f"schema:{name}", set())
    return dedupe_fields(fields)


def parse_structured_api_fields(data: Any) -> List[ApiField]:
    if isinstance(data, dict) and "fields" in data:
        data = data["fields"]
    fields: List[ApiField] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_path = first_non_empty(item.get("json_path"), item.get("path"), item.get("field"), item.get("name"), item.get("key"))
            if not raw_path:
                continue
            json_path = safe_json_path(raw_path)
            fields.append(
                ApiField(
                    json_path=json_path,
                    name=first_non_empty(item.get("name"), field_name_from_path(json_path)),
                    comment=first_non_empty(item.get("comment"), item.get("description"), item.get("desc"), item.get("note"), item.get("remark")),
                    data_type=first_non_empty(item.get("type"), item.get("data_type"), item.get("datatype")),
                    required=is_required(item.get("required")),
                    source="api_fields_json",
                )
            )
    elif isinstance(data, dict):
        walk_json_sample(data, "$", fields)
    return dedupe_fields(fields)


def walk_json_sample(value: Any, path: str, fields: List[ApiField]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
            walk_json_sample(child, child_path, fields)
    elif isinstance(value, list):
        if value:
            walk_json_sample(value[0], path + "[*]", fields)
    else:
        fields.append(ApiField(json_path=path, name=field_name_from_path(path), comment=field_name_from_path(path), data_type=type(value).__name__, required=None, source="json_sample"))


def parse_api_doc(path: str, schema_name: str = "") -> List[ApiField]:
    data = load_doc(path)
    if isinstance(data, str):
        return parse_text_fields(data)
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data or "components" in data or "definitions" in data):
        fields = parse_openapi(data, schema_name=schema_name)
        if fields:
            return fields
    return parse_structured_api_fields(data)


def dedupe_fields(fields: List[ApiField]) -> List[ApiField]:
    deduped: Dict[Tuple[str, str], ApiField] = {}
    for item in fields:
        key = (item.json_path, item.comment)
        if key not in deduped:
            deduped[key] = item
    return list(deduped.values())


def load_table_columns(path: str) -> List[TableColumn]:
    data = load_json(path)
    rows: List[Dict[str, Any]] = []
    if isinstance(data, dict) and "tables" in data:
        for table, columns in data["tables"].items():
            for col in columns:
                item = dict(col)
                item.setdefault("table", table)
                rows.append(item)
    elif isinstance(data, list):
        rows = data
    else:
        raise MappingError("columns JSON must be a list or an object with tables")
    return [column_from_row(row) for row in rows]


def column_from_row(row: Dict[str, Any]) -> TableColumn:
    return TableColumn(
        table=first_non_empty(row.get("table"), row.get("table_name")),
        column_name=first_non_empty(row.get("column_name"), row.get("column")),
        column_comment=first_non_empty(row.get("column_comment"), row.get("comment"), row.get("description")),
        data_type=first_non_empty(row.get("data_type"), row.get("type")),
        is_nullable=first_non_empty(row.get("is_nullable"), row.get("nullable")),
        numeric_scale=safe_int(row.get("numeric_scale")),
        column_default=row.get("column_default"),
        ordinal_position=safe_int(row.get("ordinal_position")) or 0,
        column_key=first_non_empty(row.get("column_key"), row.get("key")),
    )


def safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def load_db_columns(db_config: Dict[str, Any], tables: Sequence[str]) -> List[TableColumn]:
    db_type = db_config.get("type", "mysql").lower()
    if db_type == "mysql":
        try:
            import pymysql
            import pymysql.cursors
        except ImportError as exc:
            raise MappingError("MySQL column extraction requires: pip install pymysql") from exc
        password = db_config.get("password") or os.getenv(db_config.get("password_env", ""))
        conn = pymysql.connect(
            host=db_config.get("host", "127.0.0.1"),
            port=int(db_config.get("port", 3306)),
            user=db_config["user"],
            password=password or "",
            database=db_config["database"],
            charset=db_config.get("charset", "utf8mb4"),
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            markers = ",".join(["%s"] * len(tables))
            sql = f"""
SELECT TABLE_NAME AS table_name,
       COLUMN_NAME AS column_name,
       DATA_TYPE AS data_type,
       NUMERIC_SCALE AS numeric_scale,
       COLUMN_COMMENT AS column_comment,
       IS_NULLABLE AS is_nullable,
       COLUMN_DEFAULT AS column_default,
       ORDINAL_POSITION AS ordinal_position,
       COLUMN_KEY AS column_key
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s
  AND TABLE_NAME IN ({markers})
ORDER BY TABLE_NAME, ORDINAL_POSITION
"""
            cur = conn.cursor()
            cur.execute(sql, [db_config["database"], *tables])
            return [column_from_row(row) for row in cur.fetchall()]
        finally:
            conn.close()
    if db_type in {"postgres", "postgresql"}:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as exc:
            raise MappingError("PostgreSQL column extraction requires: pip install psycopg2-binary") from exc
        password = db_config.get("password") or os.getenv(db_config.get("password_env", ""))
        conn = psycopg2.connect(
            host=db_config.get("host", "127.0.0.1"),
            port=int(db_config.get("port", 5432)),
            user=db_config["user"],
            password=password or "",
            dbname=db_config["database"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        try:
            schema = db_config.get("schema", "public")
            sql = """
SELECT c.table_name,
       c.column_name,
       c.data_type,
       c.numeric_scale,
       d.description AS column_comment,
       c.is_nullable,
       c.column_default,
       c.ordinal_position,
       '' AS column_key
FROM information_schema.columns c
LEFT JOIN pg_catalog.pg_statio_all_tables st
  ON st.schemaname = c.table_schema AND st.relname = c.table_name
LEFT JOIN pg_catalog.pg_description d
  ON d.objoid = st.relid AND d.objsubid = c.ordinal_position
WHERE c.table_schema = %s
  AND c.table_name = ANY(%s)
ORDER BY c.table_name, c.ordinal_position
"""
            cur = conn.cursor()
            cur.execute(sql, [schema, list(tables)])
            return [column_from_row(row) for row in cur.fetchall()]
        finally:
            conn.close()
    if db_type == "sqlite":
        path = db_config.get("path") or db_config.get("database")
        conn = sqlite3.connect(path)
        try:
            result: List[TableColumn] = []
            for table in tables:
                if not IDENT_RE.match(table):
                    raise MappingError(f"Unsafe table name: {table}")
                rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
                for row in rows:
                    result.append(
                        TableColumn(
                            table=table,
                            column_name=row[1],
                            column_comment="",
                            data_type=row[2],
                            is_nullable="NO" if row[3] else "YES",
                            column_default=row[4],
                            ordinal_position=row[0] + 1,
                            column_key="PRI" if row[5] else "",
                        )
                    )
            return result
        finally:
            conn.close()
    raise MappingError(f"Unsupported database type for column extraction: {db_type}")


def scoped_fields(fields: Sequence[ApiField], detail_array_path: str, scope: str) -> List[ApiField]:
    detail_prefixes = {
        detail_array_path.replace("[*]", ""),
        detail_array_path.replace("[*]", "[]"),
        detail_array_path,
    }
    result: List[ApiField] = []
    for item in fields:
        in_detail = any(item.json_path.startswith(prefix + ".") or item.json_path.startswith(prefix + "[*].") for prefix in detail_prefixes)
        if scope == "detail" and in_detail:
            result.append(item)
        elif scope == "order" and not in_detail:
            result.append(item)
    return result


def relative_detail_path(path: str, detail_array_path: str) -> str:
    variants = [
        detail_array_path + "[*].",
        detail_array_path.replace("[*]", "") + "[*].",
        detail_array_path.replace("[*]", "[]") + ".",
        detail_array_path.replace("[*]", "") + ".",
    ]
    for prefix in variants:
        if path.startswith(prefix):
            return "$." + path[len(prefix) :]
    return path


def score_match(api: ApiField, column: TableColumn) -> Candidate:
    reasons: List[str] = []
    score = 0.0

    api_comment = api.comment.strip()
    col_comment = column.column_comment.strip()
    api_name = api.name or field_name_from_path(api.json_path)
    col_name = column.column_name

    api_comment_norm = normalize_text(api_comment)
    col_comment_norm = normalize_text(col_comment)
    api_name_norm = normalize_text(api_name)
    col_name_norm = normalize_text(col_name)

    if api_comment_norm and col_comment_norm:
        if api_comment_norm == col_comment_norm:
            score += 0.72
            reasons.append("字段注释完全匹配")
        elif api_comment_norm in col_comment_norm or col_comment_norm in api_comment_norm:
            score += 0.58
            reasons.append("字段注释包含匹配")
        else:
            comment_score = jaccard(split_tokens(api_comment), split_tokens(col_comment))
            if comment_score > 0:
                score += comment_score * 0.48
                reasons.append(f"字段注释相似度 {comment_score:.2f}")

    if api_name_norm and col_name_norm:
        if api_name_norm == col_name_norm:
            score += 0.48
            reasons.append("字段名完全匹配")
        else:
            name_score = jaccard(split_tokens(api_name), split_tokens(col_name))
            if name_score > 0:
                score += name_score * 0.36
                reasons.append(f"字段名相似度 {name_score:.2f}")

    if col_comment_norm:
        name_comment_score = jaccard(split_tokens(api_name), split_tokens(col_comment))
        if name_comment_score >= 0.5:
            score += name_comment_score * 0.22
            reasons.append(f"接口字段名与表注释相似度 {name_comment_score:.2f}")

    if api_comment_norm:
        column_comment_score = jaccard(split_tokens(api_comment), split_tokens(col_name))
        if column_comment_score >= 0.5:
            score += column_comment_score * 0.22
            reasons.append(f"接口注释与表字段名相似度 {column_comment_score:.2f}")

    if type_compatible(api.data_type, column.data_type):
        score += 0.08
        reasons.append("类型兼容")
    elif api.data_type and column.data_type:
        score -= 0.12
        reasons.append("类型不完全兼容")

    score = max(0.0, min(score, 1.0))
    if score >= 0.75:
        confidence = "high"
    elif score >= 0.55:
        confidence = "review"
    elif score > 0:
        confidence = "low"
    else:
        confidence = "unmatched"
    return Candidate(column=column, api_field=api, score=score, confidence=confidence, reasons=reasons)


def best_candidates(columns: Sequence[TableColumn], fields: Sequence[ApiField], excluded_columns: set) -> Tuple[List[Candidate], List[TableColumn], List[ApiField]]:
    selected: List[Candidate] = []
    matched_fields = set()
    for column in columns:
        if column.column_name in excluded_columns:
            continue
        if column.column_key.upper() == "PRI":
            continue
        candidates = [score_match(api, column) for api in fields]
        candidates.sort(key=lambda c: c.score, reverse=True)
        if candidates and candidates[0].score > 0:
            selected.append(candidates[0])
            matched_fields.add(candidates[0].api_field.json_path if candidates[0].api_field else "")
        else:
            selected.append(Candidate(column=column, api_field=None, score=0.0, confidence="unmatched", reasons=[]))

    unmatched_columns = [c.column for c in selected if c.confidence == "unmatched"]
    unmatched_fields = [field for field in fields if field.json_path not in matched_fields]
    return selected, unmatched_columns, unmatched_fields


def mapping_item(candidate: Candidate, detail_array_path: str, scope: str) -> Optional[Dict[str, Any]]:
    if not candidate.api_field or candidate.confidence in {"low", "unmatched"}:
        return None
    field_path = candidate.api_field.json_path
    if scope == "detail":
        field_path = relative_detail_path(field_path, detail_array_path)
    item: Dict[str, Any] = {
        "json_path": field_path,
        "column": candidate.column.column_name,
        "type": infer_mapping_type(candidate.column.data_type or candidate.api_field.data_type),
        "required": bool(candidate.api_field.required) or (candidate.column.is_nullable.upper() == "NO" and candidate.column.column_default is None),
        "_confidence": candidate.confidence,
        "_score": round(candidate.score, 3),
        "_match_reason": "；".join(candidate.reasons),
    }
    if item["type"] == "decimal":
        item["scale"] = candidate.column.numeric_scale if candidate.column.numeric_scale is not None else 2
    return item


def table_columns_by_name(columns: Sequence[TableColumn], table: str) -> List[TableColumn]:
    return sorted([col for col in columns if col.table == table], key=lambda c: c.ordinal_position)


def generate_config(base_config: Dict[str, Any], order_candidates: Sequence[Candidate], detail_candidates: Sequence[Candidate], detail_array_path: str) -> Dict[str, Any]:
    result = copy.deepcopy(base_config)
    result.setdefault("detail", {})["detail_array_json_path"] = detail_array_path
    result["order_field_mappings"] = [
        item for candidate in order_candidates if (item := mapping_item(candidate, detail_array_path, "order")) is not None
    ]
    result["detail_field_mappings"] = [
        item for candidate in detail_candidates if (item := mapping_item(candidate, detail_array_path, "detail")) is not None
    ]
    infer_business_key(result)
    infer_detail_match_keys(result)
    return result


def infer_business_key(config: Dict[str, Any]) -> None:
    order_cfg = config.setdefault("order", {})
    if order_cfg.get("business_key_column") and order_cfg.get("business_key_json_path"):
        return
    for item in config.get("order_field_mappings", []):
        col = item["column"].lower()
        if col in {"order_no", "order_code", "source_order_no", "order_id"} or "orderno" in normalize_text(item["json_path"]):
            order_cfg["business_key_column"] = item["column"]
            order_cfg["business_key_json_path"] = item["json_path"]
            return


def infer_detail_match_keys(config: Dict[str, Any]) -> None:
    detail_cfg = config.setdefault("detail", {})
    if detail_cfg.get("match_keys"):
        return
    preferred = ["line_no", "line_num", "sku_id", "sku_code", "item_id", "goods_id", "product_id"]
    for preferred_col in preferred:
        for item in config.get("detail_field_mappings", []):
            if item["column"].lower() == preferred_col:
                detail_cfg["match_keys"] = [
                    {
                        "json_path": item["json_path"],
                        "column": item["column"],
                        "type": item.get("type", "string"),
                        "required": item.get("required", True),
                    }
                ]
                return


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_report(
    path: str,
    fields: Sequence[ApiField],
    order_candidates: Sequence[Candidate],
    detail_candidates: Sequence[Candidate],
    unmatched_order_fields: Sequence[ApiField],
    unmatched_detail_fields: Sequence[ApiField],
) -> None:
    lines = [
        "# JSON-to-Table Mapping Draft Report",
        "",
        "## Summary",
        "",
        f"- API fields parsed: {len(fields)}",
        f"- Order candidate columns: {len(order_candidates)}",
        f"- Detail candidate columns: {len(detail_candidates)}",
        f"- Review required mappings: {sum(1 for c in list(order_candidates) + list(detail_candidates) if c.confidence == 'review')}",
        f"- Unmatched columns: {sum(1 for c in list(order_candidates) + list(detail_candidates) if c.confidence == 'unmatched')}",
        "",
        "## Order Mappings",
        "",
        mapping_table(order_candidates),
        "",
        "## Detail Mappings",
        "",
        mapping_table(detail_candidates),
        "",
        "## Unmatched API Fields",
        "",
    ]
    unmatched = list(unmatched_order_fields) + list(unmatched_detail_fields)
    if unmatched:
        lines.append("| JSON Path | Field | Comment | Type | Source |")
        lines.append("|---|---|---|---|---|")
        for item in unmatched:
            lines.append(f"| {esc(item.json_path)} | {esc(item.name)} | {esc(item.comment)} | {esc(item.data_type)} | {esc(item.source)} |")
    else:
        lines.append("No unmatched API fields.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def mapping_table(candidates: Sequence[Candidate]) -> str:
    lines = ["| Column | Column Comment | JSON Path | API Comment | Score | Confidence | Reason |", "|---|---|---|---:|---|---|---|"]
    for c in candidates:
        api = c.api_field
        lines.append(
            "| {column} | {col_comment} | {json_path} | {api_comment} | {score:.3f} | {confidence} | {reason} |".format(
                column=esc(c.column.column_name),
                col_comment=esc(c.column.column_comment or c.column.column_name),
                json_path=esc(api.json_path if api else ""),
                api_comment=esc(api.comment if api else ""),
                score=c.score,
                confidence=esc(c.confidence),
                reason=esc("；".join(c.reasons)),
            )
        )
    return "\n".join(lines)


def esc(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def default_base_config(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "database": {},
        "source": {
            "table": args.source_table,
            "id_column": args.source_id_column,
            "json_column": args.source_json_column,
            "where": "",
            "order_by": [args.source_id_column],
        },
        "order": {
            "table": args.order_table,
            "primary_key": args.order_primary_key,
            "business_key_column": "",
            "business_key_json_path": "",
            "where": "",
        },
        "detail": {
            "table": args.detail_table,
            "primary_key": args.detail_primary_key,
            "order_fk_column": args.detail_order_fk,
            "detail_array_json_path": args.detail_array_path,
            "order_by": [args.detail_primary_key],
            "match_keys": [],
        },
        "comparison": {
            "decimal_scale": 2,
            "datetime_formats": ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"],
            "timezone": "Asia/Shanghai",
            "empty_as_null": False,
        },
        "checks": {
            "source_duplicate_business_key": True,
            "orphan_details": True,
            "orphan_detail_limit": 100,
        },
    }


def run_self_test() -> None:
    api_fields = [
        ApiField("$.orderNo", "orderNo", "订单号", "string", True, "test"),
        ApiField("$.totalAmount", "totalAmount", "订单总金额", "number", True, "test"),
        ApiField("$.details[*].skuId", "skuId", "商品SKU", "string", True, "test"),
    ]
    columns = [
        TableColumn("adapter_standard_order", "order_no", "订单号", "varchar", "NO", None, None, 1, ""),
        TableColumn("adapter_standard_order", "total_amount", "订单总金额", "decimal", "NO", 2, None, 2, ""),
        TableColumn("adapter_standard_order_detail", "sku_id", "商品SKU", "varchar", "NO", None, None, 1, ""),
    ]
    order_fields = scoped_fields(api_fields, "$.details", "order")
    detail_fields = scoped_fields(api_fields, "$.details", "detail")
    order_candidates, _, _ = best_candidates(table_columns_by_name(columns, "adapter_standard_order"), order_fields, set())
    detail_candidates, _, _ = best_candidates(table_columns_by_name(columns, "adapter_standard_order_detail"), detail_fields, set())
    assert order_candidates[0].confidence == "high"
    assert detail_candidates[0].confidence == "high"
    config = generate_config(default_base_config(parse_args([])), order_candidates, detail_candidates, "$.details")
    assert config["order_field_mappings"][0]["json_path"] == "$.orderNo"
    assert config["detail_field_mappings"][0]["json_path"] == "$.skuId"
    print("self-test passed")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a reviewable JSON-to-table mapping draft.")
    parser.add_argument("--api-doc", default="", help="API document path: Markdown/TXT/OpenAPI JSON/YAML/field JSON.")
    parser.add_argument("--api-fields-json", default="", help="Pre-extracted API fields JSON path.")
    parser.add_argument("--schema-name", default="", help="OpenAPI schema name to parse when the document has many schemas.")
    parser.add_argument("--db-config", default="", help="Verification config JSON containing database/order/detail sections.")
    parser.add_argument("--columns-json", default="", help="Offline table columns JSON path.")
    parser.add_argument("--base-config", default="", help="Base verification config to update. Defaults to --db-config when omitted.")
    parser.add_argument("--detail-array-path", default="$.details", help="JSON path of detail array in source JSON.")
    parser.add_argument("--source-table", default="A")
    parser.add_argument("--source-id-column", default="id")
    parser.add_argument("--source-json-column", default="source_json")
    parser.add_argument("--order-table", default="adapter_standard_order")
    parser.add_argument("--order-primary-key", default="id")
    parser.add_argument("--detail-table", default="adapter_standard_order_detail")
    parser.add_argument("--detail-primary-key", default="id")
    parser.add_argument("--detail-order-fk", default="order_id")
    parser.add_argument("--ignore-column", action="append", default=[], help="Column to skip. Can be repeated.")
    parser.add_argument("--output-config", default="mapping-draft-config.json")
    parser.add_argument("--output-report", default="mapping-draft-report.md")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        return 0
    if not args.api_doc and not args.api_fields_json:
        print("Either --api-doc or --api-fields-json is required", file=sys.stderr)
        return 1
    if not args.db_config and not args.columns_json:
        print("Either --db-config or --columns-json is required", file=sys.stderr)
        return 1

    try:
        if args.api_fields_json:
            fields = parse_structured_api_fields(load_json(args.api_fields_json))
        else:
            fields = parse_api_doc(args.api_doc, schema_name=args.schema_name)
        if not fields:
            raise MappingError("No API fields were parsed from the document.")

        base_config_path = args.base_config or args.db_config
        base_config = load_json(base_config_path) if base_config_path else default_base_config(args)
        base_config.setdefault("order", {})["table"] = base_config.get("order", {}).get("table") or args.order_table
        base_config.setdefault("detail", {})["table"] = base_config.get("detail", {}).get("table") or args.detail_table
        detail_array_path = args.detail_array_path or base_config.get("detail", {}).get("detail_array_json_path", "$.details")

        order_table = base_config["order"]["table"]
        detail_table = base_config["detail"]["table"]
        if args.columns_json:
            columns = load_table_columns(args.columns_json)
        else:
            columns = load_db_columns(base_config["database"], [order_table, detail_table])
        if not columns:
            raise MappingError("No table columns were loaded.")

        excluded = set(TECHNICAL_COLUMNS)
        excluded.update(args.ignore_column)
        excluded.add(base_config.get("order", {}).get("primary_key", "id"))
        excluded.add(base_config.get("detail", {}).get("primary_key", "id"))
        excluded.add(base_config.get("detail", {}).get("order_fk_column", "order_id"))
        excluded.discard("")

        order_fields = scoped_fields(fields, detail_array_path, "order")
        detail_fields = scoped_fields(fields, detail_array_path, "detail")
        order_candidates, _, unmatched_order_fields = best_candidates(table_columns_by_name(columns, order_table), order_fields, excluded)
        detail_candidates, _, unmatched_detail_fields = best_candidates(table_columns_by_name(columns, detail_table), detail_fields, excluded)
        result_config = generate_config(base_config, order_candidates, detail_candidates, detail_array_path)

        write_json(args.output_config, result_config)
        write_report(args.output_report, fields, order_candidates, detail_candidates, unmatched_order_fields, unmatched_detail_fields)
    except MappingError as exc:
        print(f"mapping draft failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"mapping draft failed: {exc}", file=sys.stderr)
        return 1

    print(f"mapping_config: {Path(args.output_config).resolve()}")
    print(f"mapping_report: {Path(args.output_report).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
