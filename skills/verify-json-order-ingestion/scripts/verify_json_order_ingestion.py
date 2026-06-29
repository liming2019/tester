#!/usr/bin/env python3
"""
Read-only verifier for JSON order ingestion.

The script compares source_table.json_column with adapter order/detail tables.
It only executes SELECT statements.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


MISSING = object()
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
SQL_FRAGMENT_FORBIDDEN_RE = re.compile(
    r";|--|/\*|\*/|\b(insert|update|delete|drop|alter|truncate|merge|grant|revoke|create|replace|call|exec)\b",
    re.IGNORECASE,
)


class VerificationError(Exception):
    pass


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def quote_ident(identifier: str, db_type: str) -> str:
    parts = identifier.split(".")
    if not parts or any(not IDENT_RE.match(part) for part in parts):
        raise VerificationError(f"Unsafe identifier: {identifier!r}")
    quote = "`" if db_type == "mysql" else '"'
    return ".".join(f"{quote}{part}{quote}" for part in parts)


def qcol(alias: str, column: str, db_type: str) -> str:
    if not IDENT_RE.match(alias):
        raise VerificationError(f"Unsafe alias: {alias!r}")
    return f"{quote_ident(alias, db_type)}.{quote_ident(column, db_type)}"


def safe_sql_fragment(fragment: str, label: str) -> str:
    fragment = (fragment or "").strip()
    if not fragment:
        return ""
    lowered = fragment.lower()
    if lowered.startswith("where "):
        fragment = fragment[6:].strip()
    if lowered.startswith("order by "):
        fragment = fragment[9:].strip()
    if SQL_FRAGMENT_FORBIDDEN_RE.search(fragment):
        raise VerificationError(f"Unsafe SQL fragment in {label}: {fragment!r}")
    return fragment


def build_where(fragment: str, label: str) -> str:
    fragment = safe_sql_fragment(fragment, label)
    return f" WHERE {fragment}" if fragment else ""


def build_order_by(columns: Sequence[str], db_type: str) -> str:
    if not columns:
        return ""
    quoted = [quote_ident(str(col), db_type) for col in columns]
    return " ORDER BY " + ", ".join(quoted)


def param_marker(db_type: str) -> str:
    return "?" if db_type == "sqlite" else "%s"


def in_clause(column_sql: str, values: Sequence[Any], db_type: str) -> Tuple[str, List[Any]]:
    marker = param_marker(db_type)
    if db_type in {"postgres", "postgresql"}:
        return f"{column_sql} = ANY({marker})", [list(values)]
    return f"{column_sql} IN ({', '.join([marker] * len(values))})", list(values)


class Database:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_type = config.get("type", "mysql").lower()
        self.conn = self._connect()

    def _connect(self):
        db_type = self.db_type
        if db_type == "mysql":
            try:
                import pymysql
                import pymysql.cursors
            except ImportError as exc:
                raise VerificationError("Missing dependency: pip install pymysql") from exc
            password = self.config.get("password")
            password_env = self.config.get("password_env")
            if not password and password_env:
                password = os.getenv(password_env)
            return pymysql.connect(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 3306)),
                user=self.config["user"],
                password=password or "",
                database=self.config["database"],
                charset=self.config.get("charset", "utf8mb4"),
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=int(self.config.get("connect_timeout", 10)),
                read_timeout=int(self.config.get("read_timeout", 120)),
            )
        if db_type in {"postgres", "postgresql"}:
            try:
                import psycopg2
                import psycopg2.extras
            except ImportError as exc:
                raise VerificationError("Missing dependency: pip install psycopg2-binary") from exc
            password = self.config.get("password")
            password_env = self.config.get("password_env")
            if not password and password_env:
                password = os.getenv(password_env)
            return psycopg2.connect(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 5432)),
                user=self.config["user"],
                password=password or "",
                dbname=self.config["database"],
                connect_timeout=int(self.config.get("connect_timeout", 10)),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        if db_type == "sqlite":
            path = self.config.get("path") or self.config.get("database")
            if not path:
                raise VerificationError("SQLite config requires path or database")
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn
        raise VerificationError(f"Unsupported database type: {db_type}")

    def query(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, list(params or []))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def parse_json_path(path: str) -> List[Any]:
    if not path or path[0] != "$":
        raise VerificationError(f"JSON path must start with $: {path!r}")
    tokens: List[Any] = []
    i = 1
    while i < len(path):
        if path[i] == ".":
            j = i + 1
            while j < len(path) and path[j] not in ".[":
                j += 1
            key = path[i + 1 : j]
            if not key:
                raise VerificationError(f"Invalid JSON path: {path!r}")
            tokens.append(key)
            i = j
        elif path[i] == "[":
            j = path.find("]", i)
            if j == -1:
                raise VerificationError(f"Invalid JSON path: {path!r}")
            raw = path[i + 1 : j].strip()
            if raw.isdigit():
                tokens.append(int(raw))
            elif (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
                tokens.append(raw[1:-1])
            else:
                raise VerificationError(f"Unsupported JSON path token: {raw!r}")
            i = j + 1
        else:
            raise VerificationError(f"Invalid JSON path near {path[i:]!r}")
    return tokens


def json_get(data: Any, path: str) -> Any:
    current = data
    for token in parse_json_path(path):
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return MISSING
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                return MISSING
            current = current[token]
    return current


def is_empty(value: Any, options: Dict[str, Any]) -> bool:
    if value is MISSING or value is None:
        return True
    return bool(options.get("empty_as_null")) and value == ""


def apply_value_map(value: Any, mapping: Dict[str, Any], key: str) -> Any:
    value_map = mapping.get(key)
    if value_map is None or value is MISSING or value is None:
        return value
    return value_map.get(str(value), value)


def normalize_decimal(value: Any, scale: int) -> Optional[str]:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise VerificationError(f"Cannot parse decimal value {value!r}") from exc
    quant = Decimal("1") if scale <= 0 else Decimal("1." + ("0" * scale))
    return str(decimal_value.quantize(quant, rounding=ROUND_HALF_UP))


def parse_datetime_value(value: Any, options: Dict[str, Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, dt.date):
        parsed = dt.datetime.combine(value, dt.time.min)
    elif isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        raw = float(value)
        if raw > 10_000_000_000:
            raw = raw / 1000
        parsed = dt.datetime.fromtimestamp(raw)
    else:
        raw = str(value).strip()
        parsed = None
        for fmt in options.get("datetime_formats", []):
            try:
                parsed = dt.datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise VerificationError(f"Cannot parse datetime value {value!r}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def truthy_number(value: Any) -> bool:
    if value is MISSING or value is None or value == "":
        return False
    try:
        return Decimal(str(value)) != 0
    except (InvalidOperation, ValueError):
        return bool(value)


def apply_transform(value: Any, transform: str, mapping: Dict[str, Any], options: Dict[str, Any]) -> Any:
    if transform == "empty_to_null":
        return None if value == "" else value
    if transform == "zero_to_null":
        if value in {0, "0", 0.0, "0.0", "0.00"}:
            return None
        return value
    if transform == "cents_to_decimal":
        if value is MISSING or value is None or value == "":
            return value
        try:
            return Decimal(str(value)) / Decimal("100")
        except (InvalidOperation, ValueError) as exc:
            raise VerificationError(f"Cannot convert cents value {value!r}") from exc
    if transform == "unix_seconds_to_datetime":
        return parse_datetime_value(value, options) if value not in {MISSING, None, ""} else value
    if transform == "unix_millis_to_datetime":
        if value in {MISSING, None, ""}:
            return value
        try:
            return Decimal(str(value)) / Decimal("1000")
        except (InvalidOperation, ValueError) as exc:
            raise VerificationError(f"Cannot convert unix millis value {value!r}") from exc
    if transform == "spec_to_text":
        if value is MISSING or value is None:
            return value
        if not isinstance(value, list):
            return str(value)
        parts = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name", "")
                val = item.get("value", "")
                parts.append(f"{name}:{val}" if name != "" else str(val))
            else:
                parts.append(str(item))
        return ";".join(parts)
    if transform == "json_dumps":
        if value is MISSING or value is None:
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    raise VerificationError(f"Unsupported transform: {transform}")


def apply_transforms(value: Any, mapping: Dict[str, Any], options: Dict[str, Any], *, source: bool) -> Any:
    transforms = mapping.get("source_transforms" if source else "target_transforms")
    if transforms is None and source:
        transforms = mapping.get("transforms", [])
    if isinstance(transforms, str):
        transforms = [transforms]
    for transform in transforms or []:
        value = apply_transform(value, transform, mapping, options)
    return value


def normalize_value(value: Any, mapping: Dict[str, Any], options: Dict[str, Any], *, source: bool) -> Any:
    if value is MISSING:
        return MISSING
    if value == "" and (mapping.get("empty_as_null") or options.get("empty_as_null")):
        value = None
    value = apply_transforms(value, mapping, options, source=source)
    if source:
        value = apply_value_map(value, mapping, "value_map")
    else:
        value = apply_value_map(value, mapping, "target_value_map")
    value_type = mapping.get("type", "string")
    if value is None:
        return None
    if value_type == "string":
        text = str(value)
        return text.strip() if mapping.get("trim", False) else text
    if value_type == "int":
        return str(int(Decimal(str(value))))
    if value_type == "decimal":
        scale = int(mapping.get("scale", options.get("decimal_scale", 2)))
        return normalize_decimal(value, scale)
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
        raise VerificationError(f"Cannot parse bool value {value!r}")
    if value_type == "datetime":
        return parse_datetime_value(value, options)
    if value_type == "date":
        if isinstance(value, dt.datetime):
            return value.date().isoformat()
        if isinstance(value, dt.date):
            return value.isoformat()
        return parse_datetime_value(value, options)[:10]
    if value_type == "json":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def computed_value(source_obj: Dict[str, Any], source_row: Dict[str, Any], mapping: Dict[str, Any]) -> Any:
    name = mapping.get("computed")
    if name == "zero_order_amount":
        return not truthy_number(json_get(source_obj, "$.order_amount"))
    if name == "pre_sale_type_nonzero":
        return truthy_number(json_get(source_obj, "$.pre_sale_type"))
    if name == "source_id":
        return source_row.get("source_id")
    raise VerificationError(f"Unsupported computed source: {name}")


def get_expected_raw(source_obj: Dict[str, Any], source_row: Dict[str, Any], mapping: Dict[str, Any]) -> Any:
    if "constant" in mapping:
        return mapping["constant"]
    if mapping.get("computed"):
        return computed_value(source_obj, source_row, mapping)
    if mapping.get("source_column"):
        return source_row.get(mapping["source_column"], MISSING)
    raw = json_get(source_obj, mapping.get("json_path", "$"))
    if raw is MISSING:
        for fallback_path in mapping.get("fallback_json_paths", []):
            raw = json_get(source_obj, fallback_path)
            if raw is not MISSING:
                break
    return raw


def jsonable(value: Any) -> Any:
    if value is MISSING:
        return "<MISSING>"
    if isinstance(value, (Decimal, dt.datetime, dt.date)):
        return str(value)
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def canonical_key(values: Sequence[Any]) -> Tuple[str, ...]:
    return tuple("<NULL>" if v is None else str(v) for v in values)


def get_order_key_specs(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    order_cfg = config["order"]
    if order_cfg.get("business_keys"):
        return list(order_cfg["business_keys"])
    return [
        {
            "json_path": order_cfg["business_key_json_path"],
            "column": order_cfg["business_key_column"],
            "type": order_cfg.get("business_key_type", "string"),
            "required": True,
        }
    ]


def build_source_key(data: Dict[str, Any], specs: Sequence[Dict[str, Any]], options: Dict[str, Any]) -> Tuple[Any, ...]:
    values = []
    for spec in specs:
        raw = json_get(data, spec["json_path"])
        if raw is MISSING and "default" in spec:
            raw = spec["default"]
        values.append(normalize_value(raw, spec, options, source=True))
    return tuple(values)


def build_source_key_from_row(data: Dict[str, Any], source_row: Dict[str, Any], specs: Sequence[Dict[str, Any]], options: Dict[str, Any]) -> Tuple[Any, ...]:
    values = []
    for spec in specs:
        raw = get_expected_raw(data, source_row, spec)
        if raw is MISSING and "default" in spec:
            raw = spec["default"]
        values.append(normalize_value(raw, spec, options, source=True))
    return tuple(values)


def build_target_key(row: Dict[str, Any], specs: Sequence[Dict[str, Any]], options: Dict[str, Any]) -> Tuple[Any, ...]:
    values = []
    for spec in specs:
        raw = row.get(spec["column"], MISSING)
        values.append(normalize_value(raw, spec, options, source=False))
    return tuple(values)


def add_diff(diffs: List[Dict[str, Any]], diff_type: str, **kwargs: Any) -> None:
    item = {"type": diff_type}
    item.update({key: jsonable(value) for key, value in kwargs.items()})
    diffs.append(item)


def compare_fields(
    *,
    diffs: List[Dict[str, Any]],
    scope: str,
    source_obj: Dict[str, Any],
    source_row: Dict[str, Any],
    target_row: Dict[str, Any],
    mappings: Sequence[Dict[str, Any]],
    options: Dict[str, Any],
    source_id: Any,
    order_key: Tuple[Any, ...],
    detail_key: Optional[Tuple[Any, ...]] = None,
    detail_index: Optional[int] = None,
) -> None:
    for mapping in mappings:
        column = mapping["column"]
        raw_expected = get_expected_raw(source_obj, source_row, mapping)
        if raw_expected is MISSING and "default" in mapping:
            raw_expected = mapping["default"]

        if mapping.get("required") and is_empty(raw_expected, {**options, **mapping}):
            add_diff(
                diffs,
                f"{scope}_REQUIRED_SOURCE_VALUE_MISSING",
                source_id=source_id,
                order_key=order_key,
                detail_key=detail_key,
                detail_index=detail_index,
                json_path=mapping.get("json_path", mapping.get("source_column", mapping.get("computed", "<constant>"))),
                column=column,
            )
            continue

        if column not in target_row:
            add_diff(
                diffs,
                f"{scope}_TARGET_COLUMN_MISSING",
                source_id=source_id,
                order_key=order_key,
                detail_key=detail_key,
                detail_index=detail_index,
                column=column,
            )
            continue

        if raw_expected is MISSING and mapping.get("ignore_if_source_missing", False):
            continue

        raw_actual = target_row.get(column)
        try:
            expected = normalize_value(raw_expected, mapping, options, source=True)
            actual = normalize_value(raw_actual, mapping, options, source=False)
        except VerificationError as exc:
            add_diff(
                diffs,
                f"{scope}_NORMALIZE_ERROR",
                source_id=source_id,
                order_key=order_key,
                detail_key=detail_key,
                detail_index=detail_index,
                json_path=mapping.get("json_path", mapping.get("source_column", mapping.get("computed", "<constant>"))),
                column=column,
                error=str(exc),
                expected_raw=raw_expected,
                actual_raw=raw_actual,
            )
            continue

        if expected is MISSING:
            expected = None
        if expected != actual:
            add_diff(
                diffs,
                f"{scope}_FIELD_MISMATCH",
                source_id=source_id,
                order_key=order_key,
                detail_key=detail_key,
                detail_index=detail_index,
                json_path=mapping.get("json_path", mapping.get("source_column", mapping.get("computed", "<constant>"))),
                column=column,
                expected=expected,
                actual=actual,
                expected_raw=raw_expected,
                actual_raw=raw_actual,
            )


def fetch_source_rows(db: Database, config: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    db_type = db.db_type
    source = config["source"]
    extra_columns = []
    seen_aliases = {"source_id", "source_json"}
    for col in source.get("extra_columns", []):
        if isinstance(col, str):
            column = col
            alias = col
        else:
            column = col["column"]
            alias = col.get("alias", column)
        if alias in seen_aliases:
            continue
        extra_columns.append(f"{quote_ident(column, db_type)} AS {quote_ident(alias, db_type)}")
        seen_aliases.add(alias)
    select_parts = [
        f"{quote_ident(source['id_column'], db_type)} AS source_id",
        f"{quote_ident(source['json_column'], db_type)} AS source_json",
        *extra_columns,
    ]
    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {quote_ident(source['table'], db_type)}"
        f"{build_where(source.get('where', ''), 'source.where')}"
        f"{build_order_by(source.get('order_by', []), db_type)}"
    )
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    return db.query(sql)


def fetch_target_order(
    db: Database,
    config: Dict[str, Any],
    key_specs: Sequence[Dict[str, Any]],
    key_values: Tuple[Any, ...],
) -> List[Dict[str, Any]]:
    db_type = db.db_type
    order_cfg = config["order"]
    marker = param_marker(db_type)
    predicates = [f"{quote_ident(spec['column'], db_type)} = {marker}" for spec in key_specs]
    where = " AND ".join(predicates)
    extra = safe_sql_fragment(order_cfg.get("where", ""), "order.where")
    if extra:
        where = f"{where} AND ({extra})"
    sql = f"SELECT * FROM {quote_ident(order_cfg['table'], db_type)} WHERE {where}"
    return db.query(sql, key_values)


def bulk_key_column(specs: Sequence[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    if len(specs) != 1:
        return None
    spec = specs[0]
    if spec.get("source_column") and spec.get("column"):
        return spec["source_column"], spec["column"]
    return None


def fetch_target_orders_bulk(
    db: Database,
    config: Dict[str, Any],
    key_specs: Sequence[Dict[str, Any]],
    rows: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    bulk_key = bulk_key_column(key_specs)
    if not bulk_key:
        return None
    source_column, target_column = bulk_key
    values = [row.get(source_column) for row in rows if row.get(source_column) is not None]
    if not values:
        return {}
    db_type = db.db_type
    order_cfg = config["order"]
    column_sql = quote_ident(target_column, db_type)
    predicate, params = in_clause(column_sql, values, db_type)
    extra = safe_sql_fragment(order_cfg.get("where", ""), "order.where")
    where = predicate if not extra else f"{predicate} AND ({extra})"
    sql = f"SELECT * FROM {quote_ident(order_cfg['table'], db_type)} WHERE {where}"
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in db.query(sql, params):
        result[str(row.get(target_column))].append(row)
    return result


def fetch_target_details(db: Database, config: Dict[str, Any], source_row: Dict[str, Any], target_order: Dict[str, Any]) -> List[Dict[str, Any]]:
    db_type = db.db_type
    detail = config["detail"]
    marker = param_marker(db_type)
    source_column = detail.get("source_fk_column")
    if source_column:
        value = source_row.get(source_column, MISSING)
        if value is MISSING:
            raise VerificationError(f"detail.source_fk_column not loaded from source rows: {source_column}")
        fk_column = detail["order_fk_column"]
    else:
        order_pk = detail.get("order_pk_source_column") or config["order"]["primary_key"]
        if order_pk not in target_order:
            raise VerificationError(f"detail order lookup column missing from target order: {order_pk}")
        value = target_order[order_pk]
        fk_column = detail["order_fk_column"]
    sql = (
        f"SELECT * FROM {quote_ident(detail['table'], db_type)} "
        f"WHERE {quote_ident(fk_column, db_type)} = {marker}"
        f"{build_order_by(detail.get('order_by', []), db_type)}"
    )
    return db.query(sql, [value])


def fetch_target_details_bulk(
    db: Database,
    config: Dict[str, Any],
    rows: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    detail = config["detail"]
    source_column = detail.get("source_fk_column")
    if not source_column:
        return None
    values = [row.get(source_column) for row in rows if row.get(source_column) is not None]
    if not values:
        return {}
    db_type = db.db_type
    fk_column = detail["order_fk_column"]
    predicate, params = in_clause(quote_ident(fk_column, db_type), values, db_type)
    sql = (
        f"SELECT * FROM {quote_ident(detail['table'], db_type)} "
        f"WHERE {predicate}"
        f"{build_order_by(detail.get('order_by', []), db_type)}"
    )
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in db.query(sql, params):
        result[str(row.get(fk_column))].append(row)
    return result


def compare_details(
    *,
    diffs: List[Dict[str, Any]],
    source_id: Any,
    source_row: Dict[str, Any],
    order_key: Tuple[Any, ...],
    source_order: Dict[str, Any],
    target_details: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
) -> None:
    detail_cfg = config["detail"]
    options = config.get("comparison", {})
    mappings = config.get("detail_field_mappings", [])
    detail_array = json_get(source_order, detail_cfg["detail_array_json_path"])

    if detail_array is MISSING or detail_array is None:
        if detail_cfg.get("required", False):
            add_diff(
                diffs,
                "DETAIL_ARRAY_MISSING",
                source_id=source_id,
                order_key=order_key,
                json_path=detail_cfg["detail_array_json_path"],
            )
        detail_items: List[Dict[str, Any]] = []
    elif not isinstance(detail_array, list):
        add_diff(
            diffs,
            "DETAIL_ARRAY_NOT_LIST",
            source_id=source_id,
            order_key=order_key,
            json_path=detail_cfg["detail_array_json_path"],
            actual_type=type(detail_array).__name__,
        )
        return
    else:
        detail_items = detail_array

    if len(detail_items) != len(target_details):
        add_diff(
            diffs,
            "DETAIL_COUNT_MISMATCH",
            source_id=source_id,
            order_key=order_key,
            expected=len(detail_items),
            actual=len(target_details),
        )

    match_keys = detail_cfg.get("match_keys") or []
    if not match_keys:
        for index, source_detail in enumerate(detail_items[: len(target_details)]):
            compare_fields(
                diffs=diffs,
                scope="DETAIL",
                source_obj=source_detail,
                source_row=source_row,
                target_row=target_details[index],
                mappings=mappings,
                options=options,
                source_id=source_id,
                order_key=order_key,
                detail_key=(index,),
                detail_index=index,
            )
        return

    source_map: Dict[Tuple[str, ...], List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
    for index, source_detail in enumerate(detail_items):
        try:
            key = canonical_key(build_source_key_from_row(source_detail, source_row, match_keys, options))
        except VerificationError as exc:
            add_diff(
                diffs,
                "DETAIL_SOURCE_KEY_ERROR",
                source_id=source_id,
                order_key=order_key,
                detail_index=index,
                error=str(exc),
            )
            continue
        if any(value == "<MISSING>" for value in key):
            add_diff(
                diffs,
                "DETAIL_SOURCE_KEY_MISSING",
                source_id=source_id,
                order_key=order_key,
                detail_key=key,
                detail_index=index,
            )
        source_map[key].append((index, source_detail))

    target_map: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
    for row in target_details:
        try:
            key = canonical_key(build_target_key(row, match_keys, options))
        except VerificationError as exc:
            add_diff(
                diffs,
                "DETAIL_TARGET_KEY_ERROR",
                source_id=source_id,
                order_key=order_key,
                error=str(exc),
                row=row,
            )
            continue
        target_map[key].append(row)

    for key, rows in source_map.items():
        if len(rows) > 1:
            add_diff(diffs, "DETAIL_SOURCE_KEY_DUPLICATE", source_id=source_id, order_key=order_key, detail_key=key, count=len(rows))
    for key, rows in target_map.items():
        if len(rows) > 1:
            add_diff(diffs, "DETAIL_TARGET_KEY_DUPLICATE", source_id=source_id, order_key=order_key, detail_key=key, count=len(rows))

    for key, source_rows in source_map.items():
        if key not in target_map:
            add_diff(diffs, "DETAIL_TARGET_MISSING", source_id=source_id, order_key=order_key, detail_key=key)
            continue
        if len(source_rows) != 1 or len(target_map[key]) != 1:
            continue
        index, source_detail = source_rows[0]
        compare_fields(
            diffs=diffs,
            scope="DETAIL",
            source_obj=source_detail,
            source_row=source_row,
            target_row=target_map[key][0],
            mappings=mappings,
            options=options,
            source_id=source_id,
            order_key=order_key,
            detail_key=key,
            detail_index=index,
        )

    for key in target_map:
        if key not in source_map:
            add_diff(diffs, "DETAIL_TARGET_EXTRA", source_id=source_id, order_key=order_key, detail_key=key)


def check_orphan_details(db: Database, config: Dict[str, Any], diffs: List[Dict[str, Any]]) -> None:
    checks = config.get("checks", {})
    if not checks.get("orphan_details", False):
        return
    db_type = db.db_type
    detail = config["detail"]
    order_cfg = config["order"]
    limit = int(checks.get("orphan_detail_limit", 100))
    sql = (
        f"SELECT {qcol('d', detail['primary_key'], db_type)} AS detail_id, "
        f"{qcol('d', detail['order_fk_column'], db_type)} AS order_fk "
        f"FROM {quote_ident(detail['table'], db_type)} d "
        f"LEFT JOIN {quote_ident(order_cfg['table'], db_type)} o "
        f"ON {qcol('d', detail['order_fk_column'], db_type)} = {qcol('o', order_cfg['primary_key'], db_type)} "
        f"WHERE {qcol('o', order_cfg['primary_key'], db_type)} IS NULL "
        f"LIMIT {limit}"
    )
    for row in db.query(sql):
        add_diff(diffs, "ORPHAN_DETAIL", detail_id=row.get("detail_id"), order_fk=row.get("order_fk"))


def verify(config: Dict[str, Any], limit: int = 0) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    diffs: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {
        "source_rows": 0,
        "valid_source_json": 0,
        "orders_checked": 0,
        "details_checked": 0,
    }
    db = Database(config["database"])
    try:
        rows = fetch_source_rows(db, config, limit)
        summary["source_rows"] = len(rows)
        options = config.get("comparison", {})
        order_key_specs = get_order_key_specs(config)
        bulk_order_map = fetch_target_orders_bulk(db, config, order_key_specs, rows)
        bulk_detail_map = fetch_target_details_bulk(db, config, rows)
        source_key_counter: Counter[Tuple[str, ...]] = Counter()

        for row in rows:
            source_id = row.get("source_id")
            raw_json = row.get("source_json")
            try:
                source_obj = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            except Exception as exc:
                add_diff(diffs, "SOURCE_JSON_INVALID", source_id=source_id, error=str(exc))
                continue
            if not isinstance(source_obj, dict):
                add_diff(diffs, "SOURCE_JSON_NOT_OBJECT", source_id=source_id, actual_type=type(source_obj).__name__)
                continue

            summary["valid_source_json"] += 1
            try:
                raw_order_key = build_source_key_from_row(source_obj, row, order_key_specs, options)
                order_key = canonical_key(raw_order_key)
            except VerificationError as exc:
                add_diff(diffs, "ORDER_SOURCE_KEY_ERROR", source_id=source_id, error=str(exc))
                continue
            if any(value in {"<MISSING>", "<NULL>", ""} for value in order_key):
                add_diff(diffs, "ORDER_SOURCE_KEY_MISSING", source_id=source_id, order_key=order_key)
                continue
            source_key_counter[order_key] += 1

            if bulk_order_map is not None and len(raw_order_key) == 1:
                target_orders = bulk_order_map.get(str(raw_order_key[0]), [])
            else:
                target_orders = fetch_target_order(db, config, order_key_specs, raw_order_key)
            if len(target_orders) == 0:
                add_diff(diffs, "ORDER_TARGET_MISSING", source_id=source_id, order_key=order_key)
                continue
            if len(target_orders) > 1:
                add_diff(diffs, "ORDER_TARGET_DUPLICATE", source_id=source_id, order_key=order_key, count=len(target_orders))
                continue

            target_order = target_orders[0]
            summary["orders_checked"] += 1
            compare_fields(
                diffs=diffs,
                scope="ORDER",
                source_obj=source_obj,
                source_row=row,
                target_row=target_order,
                mappings=config.get("order_field_mappings", []),
                options=options,
                source_id=source_id,
                order_key=order_key,
            )

            if bulk_detail_map is not None:
                target_details = bulk_detail_map.get(str(source_id), [])
            else:
                try:
                    target_details = fetch_target_details(db, config, row, target_order)
                except VerificationError as exc:
                    add_diff(diffs, "DETAIL_FETCH_ERROR", source_id=source_id, order_key=order_key, error=str(exc))
                    continue
            summary["details_checked"] += len(target_details)
            compare_details(
                diffs=diffs,
                source_id=source_id,
                source_row=row,
                order_key=order_key,
                source_order=source_obj,
                target_details=target_details,
                config=config,
            )

        if config.get("checks", {}).get("source_duplicate_business_key", True):
            for key, count in source_key_counter.items():
                if count > 1:
                    add_diff(diffs, "SOURCE_BUSINESS_KEY_DUPLICATE", order_key=key, count=count)

        check_orphan_details(db, config, diffs)
    finally:
        db.close()

    summary["diff_count"] = len(diffs)
    summary["diff_type_counts"] = dict(Counter(diff["type"] for diff in diffs))
    return summary, diffs


def write_json(path: str, data: Any) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_parent_dir(path: str) -> None:
    parent = Path(path).expanduser().resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def write_markdown_report(path: str, summary: Dict[str, Any], diffs: List[Dict[str, Any]], max_diffs: int) -> None:
    lines = [
        "# JSON Order Ingestion Verification Report",
        "",
        "## Summary",
        "",
        f"- Source rows: {summary.get('source_rows', 0)}",
        f"- Valid source JSON: {summary.get('valid_source_json', 0)}",
        f"- Orders checked: {summary.get('orders_checked', 0)}",
        f"- Target details checked: {summary.get('details_checked', 0)}",
        f"- Diff count: {summary.get('diff_count', 0)}",
        "",
        "## Diff Type Counts",
        "",
    ]
    type_counts = summary.get("diff_type_counts", {})
    if type_counts:
        for diff_type, count in sorted(type_counts.items()):
            lines.append(f"- {diff_type}: {count}")
    else:
        lines.append("- No differences found.")

    lines.extend(["", "## Diff Samples", ""])
    if not diffs:
        lines.append("No differences found.")
    else:
        sample = diffs[:max_diffs]
        lines.append("| # | Type | Source ID | Order Key | Detail Key | Column | Expected | Actual | Error |")
        lines.append("|---:|---|---|---|---|---|---|---|---|")
        for index, diff in enumerate(sample, start=1):
            lines.append(
                "| {idx} | {typ} | {source_id} | {order_key} | {detail_key} | {column} | {expected} | {actual} | {error} |".format(
                    idx=index,
                    typ=escape_md(diff.get("type", "")),
                    source_id=escape_md(diff.get("source_id", "")),
                    order_key=escape_md(diff.get("order_key", "")),
                    detail_key=escape_md(diff.get("detail_key", "")),
                    column=escape_md(diff.get("column", "")),
                    expected=escape_md(diff.get("expected", "")),
                    actual=escape_md(diff.get("actual", "")),
                    error=escape_md(diff.get("error", "")),
                )
            )
        if len(diffs) > max_diffs:
            lines.append("")
            lines.append(f"Only first {max_diffs} diffs are shown. Use the diff JSON file for the full list.")

    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def escape_md(value: Any) -> str:
    text = json.dumps(jsonable(value), ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else str(jsonable(value))
    return text.replace("|", "\\|").replace("\n", " ")


RELATIONSHIP_DIFF_TYPES = {
    "ORPHAN_DETAIL",
    "SOURCE_BUSINESS_KEY_DUPLICATE",
    "ORDER_TARGET_DUPLICATE",
    "DETAIL_SOURCE_KEY_DUPLICATE",
    "DETAIL_TARGET_KEY_DUPLICATE",
}

BLOCKING_DIFF_TYPES = {
    "SOURCE_JSON_INVALID",
    "SOURCE_JSON_NOT_OBJECT",
    "DETAIL_ARRAY_NOT_LIST",
    "DETAIL_FETCH_ERROR",
    "ORDER_SOURCE_KEY_ERROR",
    "DETAIL_SOURCE_KEY_ERROR",
    "DETAIL_TARGET_KEY_ERROR",
}

DIFF_CATEGORY_LABELS = {
    "source": "源JSON/源数据问题",
    "order": "订单主表问题",
    "detail": "订单明细问题",
    "relationship": "主明细关系/幂等问题",
    "other": "其他问题",
}


def diff_category(diff_type: str) -> str:
    if diff_type in RELATIONSHIP_DIFF_TYPES:
        return "relationship"
    if diff_type.startswith("SOURCE_") or diff_type.startswith("ORDER_SOURCE_KEY"):
        return "source"
    if diff_type.startswith("ORDER_"):
        return "order"
    if diff_type.startswith("DETAIL_"):
        return "detail"
    return "other"


def is_blocking_diff(diff_type: str) -> bool:
    return (
        diff_type in BLOCKING_DIFF_TYPES
        or diff_type.endswith("_TARGET_COLUMN_MISSING")
        or diff_type.endswith("_REQUIRED_SOURCE_VALUE_MISSING")
        or diff_type.endswith("_NORMALIZE_ERROR")
    )


def display_value(value: Any, max_len: int = 160) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True)
    else:
        text = str(jsonable(value))
    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def h(value: Any, max_len: int = 160) -> str:
    return html.escape(display_value(value, max_len=max_len), quote=True)


def html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]], empty_text: str = "无") -> str:
    if not rows:
        return f'<p class="empty">{html.escape(empty_text)}</p>'
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{h(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return "<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>".format(header_html, "".join(body_rows))


def describe_key_specs(specs: Sequence[Dict[str, Any]]) -> str:
    parts = []
    for spec in specs:
        source = spec.get("json_path") or spec.get("source_column") or spec.get("computed") or "<unknown>"
        target = spec.get("column", "<unknown>")
        parts.append(f"{source} -> {target}")
    return "; ".join(parts) if parts else "未配置"


def report_scope_rows(config: Dict[str, Any]) -> List[List[Any]]:
    source = config.get("source", {})
    order = config.get("order", {})
    detail = config.get("detail", {})
    comparison = config.get("comparison", {})
    try:
        order_keys = describe_key_specs(get_order_key_specs(config))
    except Exception:
        order_keys = "配置解析失败"
    detail_match_keys = describe_key_specs(detail.get("match_keys", []))
    return [
        ["数据库类型", config.get("database", {}).get("type", "")],
        ["源表", source.get("table", "")],
        ["源主键/JSON列", f"{source.get('id_column', '')} / {source.get('json_column', '')}"],
        ["源过滤条件", source.get("where", "") or "无"],
        ["订单主表", order.get("table", "")],
        ["订单业务键", order_keys],
        ["订单过滤条件", order.get("where", "") or "无"],
        ["订单明细表", detail.get("table", "")],
        ["明细外键", detail.get("order_fk_column", "")],
        ["明细数组路径", detail.get("detail_array_json_path", "")],
        ["明细匹配键", detail_match_keys],
        ["主表字段映射数", len(config.get("order_field_mappings", []))],
        ["明细字段映射数", len(config.get("detail_field_mappings", []))],
        ["金额精度", comparison.get("decimal_scale", "")],
        ["时区", comparison.get("timezone", "")],
    ]


def diff_sample_rows(diffs: Sequence[Dict[str, Any]], max_rows: int) -> List[List[Any]]:
    rows = []
    for index, diff in enumerate(diffs[:max_rows], start=1):
        rows.append(
            [
                index,
                DIFF_CATEGORY_LABELS.get(diff_category(str(diff.get("type", ""))), "其他问题"),
                diff.get("type", ""),
                diff.get("source_id", ""),
                diff.get("order_key", ""),
                diff.get("detail_key", ""),
                diff.get("column", ""),
                diff.get("expected", ""),
                diff.get("actual", ""),
                diff.get("error", ""),
            ]
        )
    return rows


def write_html_report(
    path: str,
    config: Dict[str, Any],
    summary: Dict[str, Any],
    diffs: List[Dict[str, Any]],
    max_diffs: int,
    markdown_path: str,
    diff_json_path: str,
) -> None:
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conclusion = "通过" if not diffs else "不通过"
    conclusion_class = "pass" if not diffs else "fail"
    type_counts = Counter(diff.get("type", "") for diff in diffs)
    category_counts = Counter(diff_category(str(diff.get("type", ""))) for diff in diffs)
    blocking_diffs = [diff for diff in diffs if is_blocking_diff(str(diff.get("type", "")))]
    report_cfg = config.get("report", {})
    assumptions = report_cfg.get("assumptions", [])
    if isinstance(assumptions, str):
        assumptions = [assumptions]
    configured_blockers = report_cfg.get("blockers", [])
    if isinstance(configured_blockers, str):
        configured_blockers = [configured_blockers]

    summary_rows = [
        ["核验结论", conclusion],
        ["源数据行数", summary.get("source_rows", 0)],
        ["有效JSON行数", summary.get("valid_source_json", 0)],
        ["已核验订单数", summary.get("orders_checked", 0)],
        ["已核验目标明细数", summary.get("details_checked", 0)],
        ["差异总数", summary.get("diff_count", 0)],
        ["阻断问题数", len(blocking_diffs)],
        ["生成时间", generated_at],
    ]
    category_rows = [
        [DIFF_CATEGORY_LABELS.get(key, key), category_counts.get(key, 0)]
        for key in ["source", "order", "detail", "relationship", "other"]
        if category_counts.get(key, 0)
    ]
    type_rows = [[diff_type, count] for diff_type, count in sorted(type_counts.items())]
    artifact_rows = [
        ["HTML报告", str(Path(path).expanduser().resolve())],
        ["Markdown报告", str(Path(markdown_path).expanduser().resolve()) if markdown_path else ""],
        ["完整差异JSON", str(Path(diff_json_path).expanduser().resolve()) if diff_json_path else "未生成"],
    ]
    order_diffs = [diff for diff in diffs if diff_category(str(diff.get("type", ""))) == "order"]
    detail_diffs = [diff for diff in diffs if diff_category(str(diff.get("type", ""))) == "detail"]
    relationship_diffs = [diff for diff in diffs if diff_category(str(diff.get("type", ""))) == "relationship"]
    source_diffs = [diff for diff in diffs if diff_category(str(diff.get("type", ""))) == "source"]

    blocker_rows = diff_sample_rows(blocking_diffs, max_diffs)
    assumption_rows = [[item] for item in assumptions]
    configured_blocker_rows = [[item] for item in configured_blockers]

    css = """
body{margin:0;background:#f6f7f9;color:#1f2937;font-family:Arial,'Microsoft YaHei',sans-serif;}
.wrap{max-width:1180px;margin:0 auto;padding:24px;}
h1{font-size:24px;margin:0 0 6px;}
h2{font-size:18px;margin:26px 0 10px;border-left:4px solid #2563eb;padding-left:10px;}
.sub{color:#667085;margin:0 0 18px;}
.badge{display:inline-block;border-radius:4px;padding:4px 8px;font-weight:700;}
.pass{background:#dcfce7;color:#166534;}
.fail{background:#fee2e2;color:#991b1b;}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:12px 0;}
.metric{background:#fff;border:1px solid #e5e7eb;border-radius:6px;padding:12px;}
.metric .label{color:#667085;font-size:12px;}
.metric .value{font-size:22px;font-weight:700;margin-top:4px;}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;margin:8px 0 14px;}
th,td{border-bottom:1px solid #e5e7eb;padding:8px 10px;text-align:left;vertical-align:top;font-size:13px;word-break:break-word;}
th{background:#eef2f7;color:#344054;}
tr:last-child td{border-bottom:0;}
.empty{background:#fff;border:1px solid #e5e7eb;border-radius:6px;padding:12px;color:#667085;}
.note{color:#667085;font-size:12px;margin-top:6px;}
"""
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{h(report_cfg.get("title", "JSON订单入库核验报告"), 80)}</title>
  <style>{css}</style>
</head>
<body>
  <main class="wrap">
    <h1>{h(report_cfg.get("title", "JSON订单入库核验报告"), 80)} <span class="badge {conclusion_class}">{conclusion}</span></h1>
    <p class="sub">按总览到明细维度展示：核验结论 -> 核验范围 -> 总量统计 -> 源数据 -> 订单主表 -> 订单明细 -> 主明细关系/幂等 -> 差异样本。</p>

    <h2>1. 核验总览</h2>
    <div class="grid">
      <div class="metric"><div class="label">核验结论</div><div class="value">{conclusion}</div></div>
      <div class="metric"><div class="label">源数据行数</div><div class="value">{h(summary.get("source_rows", 0))}</div></div>
      <div class="metric"><div class="label">已核验订单数</div><div class="value">{h(summary.get("orders_checked", 0))}</div></div>
      <div class="metric"><div class="label">差异总数</div><div class="value">{h(summary.get("diff_count", 0))}</div></div>
    </div>
    {html_table(["指标", "结果"], summary_rows)}

    <h2>2. 核验范围</h2>
    {html_table(["项目", "配置"], report_scope_rows(config))}

    <h2>3. 总量与差异分布</h2>
    {html_table(["维度", "差异数"], category_rows, "无差异")}
    {html_table(["差异类型", "数量"], type_rows, "无差异")}

    <h2>4. 源JSON/源数据问题</h2>
    {html_table(["序号", "维度", "类型", "源ID", "订单键", "明细键", "字段", "期望值", "实际值", "错误"], diff_sample_rows(source_diffs, max_diffs))}

    <h2>5. 订单主表问题</h2>
    {html_table(["序号", "维度", "类型", "源ID", "订单键", "明细键", "字段", "期望值", "实际值", "错误"], diff_sample_rows(order_diffs, max_diffs))}

    <h2>6. 订单明细问题</h2>
    {html_table(["序号", "维度", "类型", "源ID", "订单键", "明细键", "字段", "期望值", "实际值", "错误"], diff_sample_rows(detail_diffs, max_diffs))}

    <h2>7. 主明细关系/幂等问题</h2>
    {html_table(["序号", "维度", "类型", "源ID", "订单键", "明细键", "字段", "期望值", "实际值", "错误"], diff_sample_rows(relationship_diffs, max_diffs))}

    <h2>8. 阻断项与假设</h2>
    {html_table(["序号", "维度", "类型", "源ID", "订单键", "明细键", "字段", "期望值", "实际值", "错误"], blocker_rows, "无阻断项")}
    {html_table(["已声明假设"], assumption_rows, "无")}
    {html_table(["外部阻塞说明"], configured_blocker_rows, "无")}

    <h2>9. 差异样本明细</h2>
    {html_table(["序号", "维度", "类型", "源ID", "订单键", "明细键", "字段", "期望值", "实际值", "错误"], diff_sample_rows(diffs, max_diffs), "无差异")}
    <p class="note">如差异超过展示上限，请以完整差异JSON为准。</p>

    <h2>10. 产物路径</h2>
    {html_table(["产物", "路径"], artifact_rows)}
  </main>
</body>
</html>
"""
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)


def run_self_test() -> None:
    sample = {
        "orderNo": "O-1",
        "totalAmount": "12.345",
        "details": [{"skuId": "SKU-1", "quantity": "2"}],
    }
    assert json_get(sample, "$.orderNo") == "O-1"
    assert json_get(sample, "$.details[0].skuId") == "SKU-1"
    assert json_get(sample, "$.missing") is MISSING
    assert normalize_value("12.345", {"type": "decimal", "scale": 2}, {}, source=True) == "12.35"
    assert normalize_value("2026-06-04 10:11:12", {"type": "datetime"}, {"datetime_formats": ["%Y-%m-%d %H:%M:%S"]}, source=True) == "2026-06-04 10:11:12"
    print("self-test passed")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify source JSON order ingestion results with read-only SELECT queries.")
    parser.add_argument("--config", help="Path to verification config JSON.")
    parser.add_argument("--output", default="json_order_ingestion_verification_report.md", help="Markdown report path.")
    parser.add_argument("--html-output", default="json_order_ingestion_verification_report.html", help="Standalone Chinese HTML report path.")
    parser.add_argument("--diff-json", default="", help="Optional full diff JSON output path.")
    parser.add_argument("--limit", type=int, default=0, help="Limit source rows for smoke verification. 0 means no limit.")
    parser.add_argument("--max-report-diffs", type=int, default=200, help="Max diff rows shown in Markdown report.")
    parser.add_argument("--self-test", action="store_true", help="Run local parser/normalizer self-test without database access.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        return 0
    if not args.config:
        print("--config is required unless --self-test is used", file=sys.stderr)
        return 1

    try:
        config = load_config(args.config)
        summary, diffs = verify(config, args.limit)
        write_markdown_report(args.output, summary, diffs, args.max_report_diffs)
        if args.html_output:
            write_html_report(args.html_output, config, summary, diffs, args.max_report_diffs, args.output, args.diff_json)
        if args.diff_json:
            write_json(args.diff_json, {"summary": summary, "diffs": diffs})
    except VerificationError as exc:
        print(f"verification setup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"report: {Path(args.output).resolve()}")
    if args.html_output:
        print(f"html_report: {Path(args.html_output).resolve()}")
    if args.diff_json:
        print(f"diff_json: {Path(args.diff_json).resolve()}")
    print(f"diff_count: {summary.get('diff_count', 0)}")
    return 2 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
