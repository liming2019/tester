#!/usr/bin/env python
import argparse
import json
import random
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


try:
    import pymysql
except Exception:
    pymysql = None

try:
    import psycopg2
    from psycopg2 import sql as pg_sql
except Exception:
    psycopg2 = None
    pg_sql = None


SUPPORTED_ENGINES = {"mysql", "postgresql"}
SAFE_STRING_PREFIXES = ("TEST_", "AUTO_", "MOCK_")


class SkillError(Exception):
    pass


@dataclass
class ColumnMeta:
    name: str
    data_type: str
    is_nullable: bool
    max_length: Optional[int]
    numeric_precision: Optional[int]
    numeric_scale: Optional[int]
    column_default: Optional[str]
    is_unique: bool
    is_primary: bool
    comment: Optional[str]


class BaseAdapter:
    engine: str

    def __init__(self, conn_cfg: Dict[str, Any]):
        self.conn_cfg = conn_cfg
        self.database = conn_cfg["database"]
        self.conn = None

    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()

    def get_columns(self, table: str) -> Dict[str, ColumnMeta]:
        raise NotImplementedError

    def fetch_reference_rows(
        self,
        table: str,
        fields: Sequence[str],
        where_clause: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def quote_ident(self, name: str) -> str:
        raise NotImplementedError

    def literal(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float, Decimal)):
            return str(value)
        if isinstance(value, datetime):
            value = value.strftime("%Y-%m-%d %H:%M:%S")
        text = str(value).replace("'", "''")
        return f"'{text}'"


class MySQLAdapter(BaseAdapter):
    engine = "mysql"

    def connect(self) -> None:
        if pymysql is None:
            raise SkillError("pymysql is not installed, cannot connect to MySQL")
        self.conn = pymysql.connect(
            host=self.conn_cfg["host"],
            port=int(self.conn_cfg.get("port", 3306)),
            user=self.conn_cfg["user"],
            password=self.conn_cfg["password"],
            database=self.database,
            charset=self.conn_cfg.get("charset", "utf8mb4"),
            cursorclass=pymysql.cursors.DictCursor,
        )

    def get_columns(self, table: str) -> Dict[str, ColumnMeta]:
        unique_map = self._load_unique_map(table)
        sql = """
        SELECT
          COLUMN_NAME,
          DATA_TYPE,
          IS_NULLABLE,
          CHARACTER_MAXIMUM_LENGTH,
          NUMERIC_PRECISION,
          NUMERIC_SCALE,
          COLUMN_DEFAULT,
          COLUMN_KEY,
          COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """
        with self.conn.cursor() as cursor:
            cursor.execute(sql, (self.database, table))
            rows = cursor.fetchall()
        if not rows:
            raise SkillError(f"Target table not found: {self.database}.{table}")
        result = {}
        for row in rows:
            name = row["COLUMN_NAME"]
            key = row["COLUMN_KEY"] or ""
            result[name] = ColumnMeta(
                name=name,
                data_type=(row["DATA_TYPE"] or "").lower(),
                is_nullable=(row["IS_NULLABLE"] == "YES"),
                max_length=row["CHARACTER_MAXIMUM_LENGTH"],
                numeric_precision=row["NUMERIC_PRECISION"],
                numeric_scale=row["NUMERIC_SCALE"],
                column_default=row["COLUMN_DEFAULT"],
                is_unique=unique_map.get(name, False) or key in {"PRI", "UNI"},
                is_primary=(key == "PRI"),
                comment=row.get("COLUMN_COMMENT"),
            )
        return result

    def _load_unique_map(self, table: str) -> Dict[str, bool]:
        sql = """
        SELECT COLUMN_NAME, NON_UNIQUE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        """
        with self.conn.cursor() as cursor:
            cursor.execute(sql, (self.database, table))
            rows = cursor.fetchall()
        result: Dict[str, bool] = {}
        for row in rows:
            if row["NON_UNIQUE"] == 0:
                result[row["COLUMN_NAME"]] = True
        return result

    def fetch_reference_rows(
        self,
        table: str,
        fields: Sequence[str],
        where_clause: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        field_sql = ", ".join(self.quote_ident(f) for f in fields)
        query = f"SELECT {field_sql} FROM {self.quote_ident(self.database)}.{self.quote_ident(table)}"
        if where_clause:
            query += f" {where_clause.strip()}"
        query += f" LIMIT {int(limit)}"
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def quote_ident(self, name: str) -> str:
        return "`" + name.replace("`", "``") + "`"


class PostgreSQLAdapter(BaseAdapter):
    engine = "postgresql"

    def connect(self) -> None:
        if psycopg2 is None:
            raise SkillError("psycopg2 is not installed, cannot connect to PostgreSQL")
        self.conn = psycopg2.connect(
            host=self.conn_cfg["host"],
            port=int(self.conn_cfg.get("port", 5432)),
            user=self.conn_cfg["user"],
            password=self.conn_cfg["password"],
            dbname=self.database,
        )

    def get_columns(self, table: str) -> Dict[str, ColumnMeta]:
        unique_map, primary_map = self._load_constraint_map(table)
        sql = """
        SELECT
          column_name,
          data_type,
          is_nullable,
          character_maximum_length,
          numeric_precision,
          numeric_scale,
          column_default,
          pgd.description
        FROM information_schema.columns
        LEFT JOIN pg_catalog.pg_statio_all_tables st
          ON st.schemaname = current_schema()
         AND st.relname = columns.table_name
        LEFT JOIN pg_catalog.pg_description pgd
          ON pgd.objoid = st.relid
         AND pgd.objsubid = columns.ordinal_position
        WHERE table_schema = current_schema()
          AND table_name = %s
        ORDER BY ordinal_position
        """
        with self.conn.cursor() as cursor:
            cursor.execute(sql, (table,))
            rows = cursor.fetchall()
        if not rows:
            raise SkillError(f"Target table not found in current schema: {self.database}.{table}")
        result = {}
        for row in rows:
            name = row[0]
            result[name] = ColumnMeta(
                name=name,
                data_type=(row[1] or "").lower(),
                is_nullable=(row[2] == "YES"),
                max_length=row[3],
                numeric_precision=row[4],
                numeric_scale=row[5],
                column_default=row[6],
                is_unique=unique_map.get(name, False) or primary_map.get(name, False),
                is_primary=primary_map.get(name, False),
                comment=row[7],
            )
        return result

    def _load_constraint_map(self, table: str) -> Tuple[Dict[str, bool], Dict[str, bool]]:
        sql = """
        SELECT
          kcu.column_name,
          tc.constraint_type
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = %s
          AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
        """
        unique_map: Dict[str, bool] = {}
        primary_map: Dict[str, bool] = {}
        with self.conn.cursor() as cursor:
            cursor.execute(sql, (table,))
            for column_name, constraint_type in cursor.fetchall():
                if constraint_type == "PRIMARY KEY":
                    primary_map[column_name] = True
                if constraint_type == "UNIQUE":
                    unique_map[column_name] = True
        return unique_map, primary_map

    def fetch_reference_rows(
        self,
        table: str,
        fields: Sequence[str],
        where_clause: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        field_sql = ", ".join(self.quote_ident(f) for f in fields)
        query = f"SELECT {field_sql} FROM {self.quote_ident(table)}"
        if where_clause:
            query += f" {where_clause.strip()}"
        query += f" LIMIT {int(limit)}"
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def quote_ident(self, name: str) -> str:
        return '"' + name.replace('"', '""') + '"'


def make_adapter(conn_cfg: Dict[str, Any]) -> BaseAdapter:
    engine = conn_cfg.get("engine")
    if engine not in SUPPORTED_ENGINES:
        raise SkillError(
            f"Unsupported engine: {engine}. Currently supported engines: {', '.join(sorted(SUPPORTED_ENGINES))}"
        )
    adapter_cls = MySQLAdapter if engine == "mysql" else PostgreSQLAdapter
    adapter = adapter_cls(conn_cfg)
    adapter.connect()
    return adapter


def load_config(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SkillError(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SkillError(f"Invalid JSON config: {exc}")


def validate_config(cfg: Dict[str, Any]) -> None:
    for section in ("target", "reference"):
        if section not in cfg:
            raise SkillError(f"Missing config section: {section}")
        for key in ("connection", "table"):
            if key not in cfg[section]:
                raise SkillError(f"Missing config key: {section}.{key}")
        for key in ("engine", "host", "port", "database", "user", "password"):
            if key not in cfg[section]["connection"]:
                raise SkillError(f"Missing config key: {section}.connection.{key}")

    if "mappings" not in cfg or not cfg["mappings"]:
        raise SkillError("At least one field mapping is required")
    if "row_count" not in cfg or int(cfg["row_count"]) <= 0:
        raise SkillError("row_count must be a positive integer")

    filters = cfg["reference"].get("where", "").strip()
    if filters and not filters.upper().startswith("WHERE "):
        raise SkillError("reference.where must start with 'WHERE ' when provided")

    insert_mode = str(cfg.get("insert_mode", "full")).lower()
    if insert_mode not in {"full", "minimal", "custom"}:
        raise SkillError("insert_mode must be one of: full, minimal, custom")
    if insert_mode == "custom" and not cfg.get("target", {}).get("insert_fields"):
        raise SkillError("target.insert_fields is required when insert_mode is custom")


def normalize_generation_rules(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rules = cfg.get("generation_rules", {})
    if not isinstance(rules, dict):
        raise SkillError("generation_rules must be a JSON object")
    return rules


def build_reference_fields(mappings: Sequence[Dict[str, str]]) -> List[str]:
    fields: List[str] = []
    for item in mappings:
        for key in ("target_field", "reference_field"):
            if key not in item:
                raise SkillError(f"Mapping is missing {key}")
        ref_field = item["reference_field"]
        if ref_field not in fields:
            fields.append(ref_field)
    return fields


def build_mapping_index(mappings: Sequence[Dict[str, str]]) -> Dict[str, str]:
    result = {}
    for item in mappings:
        result[item["target_field"]] = item["reference_field"]
    return result


def infer_insert_fields(
    target_columns: Dict[str, ColumnMeta],
    mapping_index: Dict[str, str],
    generation_rules: Dict[str, Dict[str, Any]],
    explicit_fields: Optional[Sequence[str]],
    insert_mode: str,
) -> List[str]:
    if insert_mode == "custom":
        if not explicit_fields:
            raise SkillError("insert_mode=custom requires explicit insert_fields")
        return list(explicit_fields)
    fields = []
    for name, meta in target_columns.items():
        if name in mapping_index:
            fields.append(name)
            continue
        if name in generation_rules:
            fields.append(name)
            continue
        if meta.is_primary:
            continue
        if insert_mode == "minimal":
            if meta.column_default is not None:
                continue
            fields.append(name)
            continue
        auto_time_default = (meta.column_default or "").upper()
        if auto_time_default.startswith("CURRENT_TIMESTAMP"):
            continue
        fields.append(name)
    if not fields:
        raise SkillError("No insert fields could be determined")
    return fields


def normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def has_any(text: str, keywords: Sequence[str]) -> bool:
    return any(word in text for word in keywords)


def is_metric_field(field: str, comment: Optional[str], keywords: Sequence[str]) -> bool:
    text = f"{field.lower()} {normalize_text(comment)}"
    return has_any(text, keywords)


def infer_rule_from_comment_or_name(field: str, meta: ColumnMeta) -> Optional[Dict[str, Any]]:
    text = f"{field.lower()} {normalize_text(meta.comment)}"

    if has_any(text, ["展示次数", "曝光", "show_count", "impression", "impressions", "view_count"]):
        return {"type": "int_range", "min": 1000, "max": 10000}

    if has_any(text, ["点击次数", "click_count", "clicks", "点击数"]):
        return {"type": "int_range", "min": 100, "max": 2000}

    if has_any(text, ["订单数", "order_count", "成交单量", "成交订单数", "支付订单数", "转化数"]):
        return {"type": "int_range", "min": 10, "max": 300}

    if has_any(text, ["点击率", "ctr", "cvr_rate"]) or has_any(text, ["click-through rate"]):
        return {"type": "decimal_range", "min": 0.01, "max": 0.3}

    if has_any(text, ["转化率", "convert_rate", "conversion rate", "cvt_rate"]):
        return {"type": "decimal_range", "min": 0.01, "max": 0.2}

    if has_any(text, ["roi", "投入产出比"]):
        return {"type": "decimal_range", "min": 0.8, "max": 5}

    if has_any(text, ["成本", "cost_per", "cpa", "cpc", "cost"]) and meta.data_type in {
        "decimal",
        "numeric",
        "double",
        "float",
        "real",
    }:
        return {"type": "decimal_range", "min": 1, "max": 500}

    if has_any(text, ["状态", "status", "state"]) and meta.data_type in {
        "varchar",
        "char",
        "text",
        "nvarchar",
    }:
        return {"type": "fixed", "value": "CREATED"}

    if has_any(text, ["备注", "remark", "memo", "comment", "说明", "desc"]):
        return {"type": "fixed", "value": "auto test data"}

    if has_any(text, ["时间", "date", "time", "创建", "create", "update", "modified"]):
        return {
            "type": "datetime",
            "mode": "offset_now",
            "seconds_per_row": 1 if meta.is_unique else 0,
            "format": "%Y-%m-%d %H:%M:%S",
        }

    if has_any(text, ["金额", "gmv", "amount", "amt", "price", "fee", "balance", "消耗", "补贴"]):
        return {"type": "decimal_range", "min": 100, "max": 100000}

    if has_any(text, ["id", "编号", "编码", "code", "no", "number", "sn", "order_id", "biz_id"]):
        prefix = re.sub(r"[^A-Za-z]", "", field).upper()[:8] or "AUTO"
        if meta.data_type in {"bigint", "int", "integer", "smallint"}:
            return {"type": "int_range", "min": 100000, "max": 999999999}
        return {"type": "sequence", "prefix": f"{prefix}{datetime.now().strftime('%Y%m%d')}", "start": 1, "width": 3}

    if has_any(text, ["姓名", "名称", "name", "title"]):
        return {"type": "fixed", "value": "TEST_NAME"}

    if has_any(text, ["手机", "mobile", "phone", "tel"]):
        return {"type": "sequence", "prefix": "1390000", "start": 1000, "width": 4}

    if has_any(text, ["邮箱", "email", "mail"]):
        return {"type": "sequence", "prefix": "autotest", "start": 1, "width": 3}

    if has_any(text, ["地址", "address"]):
        return {"type": "fixed", "value": "TEST_ADDRESS"}

    if has_any(text, ["类型", "type", "category"]):
        return {"type": "fixed", "value": "TEST"}

    if meta.is_unique and meta.data_type in {"varchar", "char", "text", "nvarchar"}:
        prefix = re.sub(r"[^A-Za-z]", "", field).upper()[:8] or "AUTO"
        return {"type": "sequence", "prefix": f"{prefix}{datetime.now().strftime('%Y%m%d')}", "start": 1, "width": 4}

    return None


def format_decimal(value: Decimal, scale: Optional[int]) -> Decimal:
    if scale is None:
        return value
    quant = Decimal("1." + ("0" * scale))
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def compute_business_metrics(row_index: int) -> Dict[str, Any]:
    impressions = random.randint(1000, 10000)
    ctr = Decimal(str(random.uniform(0.03, 0.2)))
    clicks = max(1, int(impressions * float(ctr)))
    clicks = min(clicks, impressions)

    cvr = Decimal(str(random.uniform(0.01, 0.15)))
    orders = max(1, int(clicks * float(cvr)))
    orders = min(orders, clicks)

    avg_order_gmv = Decimal(str(random.uniform(30, 500)))
    gmv = Decimal(orders) * avg_order_gmv

    roi = Decimal(str(random.uniform(1.0, 4.5)))
    cost = gmv / roi if roi != 0 else gmv
    cost_per_order = cost / Decimal(orders) if orders else cost

    unfinished_gmv = gmv * Decimal(str(random.uniform(0.05, 0.3)))
    coupon_amount = gmv * Decimal(str(random.uniform(0.01, 0.08)))
    subsidy_amount = gmv * Decimal(str(random.uniform(0.01, 0.05)))
    gmv_include_coupon = gmv + coupon_amount

    return {
        "impressions": impressions,
        "clicks": clicks,
        "orders": orders,
        "ctr": ctr,
        "cvr": cvr,
        "gmv": gmv,
        "roi": roi,
        "cost": cost,
        "cost_per_order": cost_per_order,
        "unfinished_gmv": unfinished_gmv,
        "coupon_amount": coupon_amount,
        "subsidy_amount": subsidy_amount,
        "gmv_include_coupon": gmv_include_coupon,
    }


def metric_value_for_field(field: str, meta: ColumnMeta, metrics: Dict[str, Any]) -> Optional[Any]:
    if is_metric_field(field, meta.comment, ["展示次数", "曝光", "show_count", "impression", "impressions", "view_count"]):
        return metrics["impressions"]
    if is_metric_field(field, meta.comment, ["点击次数", "click_count", "clicks", "点击数"]):
        return metrics["clicks"]
    if is_metric_field(field, meta.comment, ["订单数", "order_count", "成交单量", "成交订单数", "支付订单数", "转化数"]):
        return metrics["orders"]
    if normalize_text(meta.comment).find("点击率") >= 0 or field.lower().find("cvr_rate") >= 0:
        return format_decimal(metrics["ctr"], meta.numeric_scale)
    if normalize_text(meta.comment).find("转化率") >= 0 or field.lower().find("convert_rate") >= 0:
        return format_decimal(metrics["cvr"], meta.numeric_scale)
    if normalize_text(meta.comment).find("roi") >= 0 or normalize_text(meta.comment).find("投入产出比") >= 0:
        return format_decimal(metrics["roi"], meta.numeric_scale)
    if normalize_text(meta.comment).find("整体消耗") >= 0 or (
        normalize_text(meta.comment).find("消耗") >= 0 and normalize_text(meta.comment).find("成本") < 0
    ):
        return format_decimal(metrics["cost"], meta.numeric_scale)
    if normalize_text(meta.comment).find("成本") >= 0 or field.lower().find("cost_per") >= 0:
        return format_decimal(metrics["cost_per_order"], meta.numeric_scale)
    if normalize_text(meta.comment).find("未完结预售订单预估金额") >= 0 or field.lower().find("unfinished") >= 0:
        return format_decimal(metrics["unfinished_gmv"], meta.numeric_scale)
    if normalize_text(meta.comment).find("优惠券金额") >= 0 or field.lower().find("coupon") >= 0:
        return format_decimal(metrics["coupon_amount"], meta.numeric_scale)
    if normalize_text(meta.comment).find("平台补贴金额") >= 0 or (
        normalize_text(meta.comment).find("补贴") >= 0 and normalize_text(meta.comment).find("金额") >= 0
    ):
        return format_decimal(metrics["subsidy_amount"], meta.numeric_scale)
    if (
        normalize_text(meta.comment).find("成交金额") >= 0
        or normalize_text(meta.comment).find("支付金额") >= 0
        or normalize_text(meta.comment).find("实际支付金额") >= 0
    ) and normalize_text(meta.comment).find("未完结") < 0 and normalize_text(meta.comment).find("优惠券") < 0 and normalize_text(meta.comment).find("补贴") < 0:
        if field.lower().find("include_coupon") >= 0:
            return format_decimal(metrics["gmv_include_coupon"], meta.numeric_scale)
        return format_decimal(metrics["gmv"], meta.numeric_scale)

    return None


def parse_datetime_rule(rule: Dict[str, Any], index: int) -> str:
    mode = rule.get("mode", "now")
    if mode == "now":
        dt = datetime.now()
    elif mode == "offset_now":
        seconds = int(rule.get("seconds_per_row", 0)) * index
        dt = datetime.now() + timedelta(seconds=seconds)
    elif mode == "fixed":
        if "value" not in rule:
            raise SkillError("datetime fixed rule requires value")
        return str(rule["value"])
    else:
        raise SkillError(f"Unsupported datetime mode: {mode}")
    return dt.strftime(rule.get("format", "%Y-%m-%d %H:%M:%S"))


def generate_value(
    field: str,
    meta: ColumnMeta,
    rule: Optional[Dict[str, Any]],
    row_index: int,
    used_values: Dict[str, set],
) -> Any:
    if rule is None:
        rule = infer_rule_from_comment_or_name(field, meta)

    if rule:
        rule_type = rule.get("type")
        if rule_type == "fixed":
            value = rule.get("value")
            if has_any(field.lower(), ["email", "mail"]) and "@" not in str(value):
                return f"{value.lower()}{row_index + 1:03d}@example.com"
            return value
        if rule_type == "sequence":
            prefix = str(rule.get("prefix", "AUTO"))
            start = int(rule.get("start", 1))
            width = int(rule.get("width", 0))
            value = start + row_index
            text = f"{prefix}{value:0{width}d}" if width > 0 else f"{prefix}{value}"
            if has_any(field.lower(), ["email", "mail"]):
                return f"{text.lower()}@example.com"
            return text
        if rule_type == "enum":
            values = rule.get("values") or []
            if not values:
                raise SkillError(f"enum rule for {field} requires values")
            return values[row_index % len(values)]
        if rule_type == "decimal_range":
            min_value = Decimal(str(rule["min"]))
            max_value = Decimal(str(rule["max"]))
            raw = Decimal(str(random.uniform(float(min_value), float(max_value))))
            return format_decimal(raw, meta.numeric_scale)
        if rule_type == "int_range":
            return random.randint(int(rule["min"]), int(rule["max"]))
        if rule_type == "datetime":
            return parse_datetime_rule(rule, row_index)
        if rule_type == "uuid":
            return uuid.uuid4().hex
        if rule_type == "null":
            if not meta.is_nullable:
                raise SkillError(f"Field {field} is not nullable, cannot use null rule")
            return None
        raise SkillError(f"Unsupported generation rule type for {field}: {rule_type}")

    data_type = meta.data_type
    if meta.column_default is not None:
        raise SkillError(f"Field {field} should rely on database default, not literal generation")
    if meta.is_nullable:
        return None

    if data_type in {"varchar", "char", "text", "mediumtext", "longtext", "nvarchar"}:
        max_len = meta.max_length or 32
        base = SAFE_STRING_PREFIXES[row_index % len(SAFE_STRING_PREFIXES)] + field.upper()
        suffix = f"_{row_index + 1}"
        value = (base + suffix)[:max_len]
        if not value:
            raise SkillError(f"Could not generate safe string for field {field}")
        return value
    if data_type in {"bigint", "int", "integer", "smallint"}:
        return row_index + 1
    if data_type in {"decimal", "numeric", "double", "float", "real"}:
        return format_decimal(Decimal("1.00") + Decimal(row_index), meta.numeric_scale)
    if data_type in {"datetime", "timestamp", "date"}:
        dt = datetime.now() + timedelta(seconds=row_index if meta.is_unique else 0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if data_type in {"bit", "boolean", "bool", "tinyint"}:
        return 1

    raise SkillError(
        f"Field '{field}' has unsupported type '{data_type}' without an explicit generation rule"
    )


def enforce_uniqueness(field: str, value: Any, meta: ColumnMeta, used_values: Dict[str, set]) -> None:
    if not meta.is_unique:
        return
    bucket = used_values.setdefault(field, set())
    if value in bucket:
        raise SkillError(f"Generated duplicate value for unique field '{field}': {value}")
    bucket.add(value)


def build_rows(
    insert_fields: Sequence[str],
    target_columns: Dict[str, ColumnMeta],
    reference_rows: Sequence[Dict[str, Any]],
    mapping_index: Dict[str, str],
    generation_rules: Dict[str, Dict[str, Any]],
) -> List[List[Any]]:
    rows: List[List[Any]] = []
    used_values: Dict[str, set] = {}
    for row_index, ref_row in enumerate(reference_rows):
        metrics = compute_business_metrics(row_index)
        current: List[Any] = []
        for field in insert_fields:
            meta = target_columns[field]
            if field in mapping_index:
                value = ref_row.get(mapping_index[field])
                if value is None and not meta.is_nullable:
                    raise SkillError(
                        f"Reference value for non-null field '{field}' is null; check reference filter or source data"
                    )
            else:
                user_rule = generation_rules.get(field)
                if user_rule is not None:
                    value = generate_value(field, meta, user_rule, row_index, used_values)
                else:
                    metric_value = metric_value_for_field(field, meta, metrics)
                    if metric_value is not None:
                        value = metric_value
                    else:
                        value = generate_value(field, meta, None, row_index, used_values)
            enforce_uniqueness(field, value, meta, used_values)
            current.append(value)
        rows.append(current)
    return rows


def expand_reference_rows(reference_rows: Sequence[Dict[str, Any]], row_count: int) -> List[Dict[str, Any]]:
    if not reference_rows:
        raise SkillError("Reference query returned no rows")
    expanded: List[Dict[str, Any]] = []
    idx = 0
    while len(expanded) < row_count:
        expanded.append(reference_rows[idx % len(reference_rows)])
        idx += 1
    return expanded


def build_insert_sql(
    adapter: BaseAdapter,
    table: str,
    insert_fields: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> str:
    quoted_fields = ", ".join(adapter.quote_ident(f) for f in insert_fields)
    values_sql = []
    for row in rows:
        values_sql.append("(" + ", ".join(adapter.literal(v) for v in row) + ")")
    table_sql = f"{adapter.quote_ident(adapter.database)}.{adapter.quote_ident(table)}"
    return f"INSERT INTO {table_sql} ({quoted_fields})\nVALUES\n  " + ",\n  ".join(values_sql) + ";"


def render_summary(cfg: Dict[str, Any], insert_fields: Sequence[str], note_lines: Sequence[str]) -> str:
    mappings = cfg["mappings"]
    mapping_text = "; ".join(
        f"{item['target_field']} -> {cfg['reference']['table']}.{item['reference_field']}" for item in mappings
    )
    rules = cfg.get("generation_rules", {})
    if rules:
        rule_text = "; ".join(f"{field}:{rule.get('type', 'unknown')}" for field, rule in rules.items())
    else:
        rule_text = "auto by column comment/name/type"
    notes = "; ".join(note_lines) if note_lines else "none"
    return "\n".join(
        [
            "Configuration Summary",
            f"1. Target database and table: {cfg['target']['connection']['database']}.{cfg['target']['table']}",
            f"2. Insert fields: {', '.join(insert_fields)}",
            f"3. Reference database and table: {cfg['reference']['connection']['database']}.{cfg['reference']['table']}",
            f"4. Filter: {cfg['reference'].get('where', '(none)') or '(none)'}",
            f"5. Field mappings: {mapping_text}",
            f"6. Row count: {cfg['row_count']}",
            f"7. Insert mode: {cfg.get('insert_mode', 'full')}",
            f"8. Generation rules: {rule_text}",
            f"9. Constraint notes: {notes}",
            "",
            "Executable INSERT SQL",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate test-data INSERT SQL from live database metadata")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    parser.add_argument("--check-config", action="store_true", help="Validate config only, do not connect to DB")
    args = parser.parse_args()

    try:
        cfg = load_config(Path(args.config))
        validate_config(cfg)
        if args.check_config:
            print("Config is valid.")
            return 0

        generation_rules = normalize_generation_rules(cfg)
        mapping_index = build_mapping_index(cfg["mappings"])
        reference_fields = build_reference_fields(cfg["mappings"])
        insert_mode = str(cfg.get("insert_mode", "full")).lower()

        target_adapter = make_adapter(cfg["target"]["connection"])
        reference_adapter = None
        try:
            if cfg["reference"]["connection"] == cfg["target"]["connection"]:
                reference_adapter = target_adapter
            else:
                reference_adapter = make_adapter(cfg["reference"]["connection"])

            target_columns = target_adapter.get_columns(cfg["target"]["table"])
            for field in mapping_index:
                if field not in target_columns:
                    raise SkillError(f"Mapped target field not found: {field}")

            insert_fields = infer_insert_fields(
                target_columns,
                mapping_index,
                generation_rules,
                cfg.get("target", {}).get("insert_fields"),
                insert_mode,
            )
            for field in insert_fields:
                if field not in target_columns:
                    raise SkillError(f"Insert field not found in target metadata: {field}")

            fetch_limit = int(cfg["row_count"])
            unique_reference_mode = bool(cfg.get("reference", {}).get("require_distinct_reference_rows", True))
            extra_limit = fetch_limit * 3 if unique_reference_mode else fetch_limit
            reference_rows = reference_adapter.fetch_reference_rows(
                cfg["reference"]["table"],
                reference_fields,
                cfg["reference"].get("where", ""),
                extra_limit,
            )
            if not reference_rows:
                raise SkillError("Reference query returned no rows")

            if unique_reference_mode:
                deduped = []
                seen = set()
                for row in reference_rows:
                    key = tuple(row.get(f) for f in reference_fields)
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(row)
                    if len(deduped) >= fetch_limit:
                        break
                reference_rows = deduped

            if unique_reference_mode and len(reference_rows) < fetch_limit:
                raise SkillError(
                    f"Reference rows are insufficient for requested row_count={fetch_limit}; only {len(reference_rows)} legal rows found"
                )
            if unique_reference_mode:
                reference_rows = reference_rows[:fetch_limit]
            else:
                reference_rows = expand_reference_rows(reference_rows, fetch_limit)

            rows = build_rows(insert_fields, target_columns, reference_rows, mapping_index, generation_rules)
            sql = build_insert_sql(target_adapter, cfg["target"]["table"], insert_fields, rows)

            note_lines = [
                f"target engine={cfg['target']['connection']['engine']}",
                f"reference engine={cfg['reference']['connection']['engine']}",
                "linked fields sourced from live reference query",
            ]
            print(render_summary(cfg, insert_fields, note_lines))
            print(sql)
            return 0
        finally:
            if reference_adapter is not None and reference_adapter is not target_adapter:
                reference_adapter.close()
            target_adapter.close()
    except SkillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
