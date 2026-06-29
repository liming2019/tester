---
name: quick-build-test-data
description: 根据实时数据库元数据、业务规则、参考表约束和字段映射，生成可直接执行的测试数据 INSERT SQL。适用于 Codex 需要连接目标库与参考库、自动读取表结构、按精确 WHERE 条件获取合法关联值，并输出“配置说明 + 可执行 SQL”结果的场景。
---

# 快速构建测试数据

## 概述

优先使用内置脚本直接连库，自动读取目标表元数据、查询参考表合法取值，并生成可直接执行的 `INSERT` SQL。

当用户能提供数据库连接信息时，优先走脚本工作流；只有在无法连库时，才退回到手工拼装 SQL 的模式。

## 当前支持的数据库

当前脚本支持：

- MySQL via `pymysql`
- PostgreSQL via `psycopg2`

在脚本未扩展前，不要声称支持 Oracle 或 SQL Server。

## 核心规则

严格遵守以下规则：

1. 原样保留用户提供的 `WHERE` 条件，不修改、不放宽、不重写。
2. 所有映射字段都必须来自实时参考查询结果，禁止伪造关联值。
3. 非关联字段默认根据字段注释、字段名和字段类型自动生成；只有自动策略无法安全判断时，才要求用户补充规则。
4. 在当前可获取元数据范围内，尽量严格满足字段类型、长度、可空性和单字段唯一性约束。
5. 不生成真实敏感个人信息。
6. 只输出可执行 SQL，不输出伪 SQL。
7. 最终响应必须固定为两段：
   - 配置说明
   - 可直接执行的 `INSERT` SQL

## 插入模式

支持以下 `insert_mode`：

- `full`
  默认模式。除自增主键、`CURRENT_TIMESTAMP` 这类明显自动维护字段外，尽量把目标表业务字段全部显式写入 `INSERT`，即使这些字段在数据库里有默认值。
- `minimal`
  只生成成功插入所必需的字段；有默认值的字段默认跳过。
- `custom`
  仅生成 `target.insert_fields` 中显式指定的字段。

## 推荐工作流

### 第一步：整理配置

优先向用户收集以下信息：

- 目标库连接
- 参考库连接
- 目标表
- 字段映射关系
- 精确的参考 `WHERE` 条件
- 生成条数
- 插入模式
- 非关联字段生成规则（可选，仅用于覆盖自动策略）

优先整理成 [config-template.json](references/config-template.json) 的 JSON 结构。

默认不需要用户提供 `insert_fields`。脚本会直接读取目标表结构，并按 `insert_mode` 决定插入字段：

- `full`：除自增主键、`CURRENT_TIMESTAMP` 自动维护字段外，尽量全部纳入插入，即使字段本身有默认值
- `minimal`：映射字段和无默认值字段纳入插入，有默认值字段默认跳过
- `custom`：仅插入 `target.insert_fields` 指定字段

非关联字段默认生成策略：

- 优先读取字段注释中的语义信息
- 其次根据字段名关键词判断，如 `status`、`amount`、`create_time`、`remark`
- 最后按字段类型回退生成安全测试值

只有在字段语义复杂、自动策略无法安全判断时，才要求用户额外提供生成规则。

如果用户是自然语言描述，先转换成同样的内部配置结构，再执行脚本。

### 第二步：校验配置

执行：

```powershell
python .\scripts\generate_test_data_sql.py --config .\references\config-template.json --check-config
```

当请求较复杂或信息边界不清时，先执行 `--check-config`。

### 第三步：生成 SQL

执行：

```powershell
python .\scripts\generate_test_data_sql.py --config <path-to-config.json>
```

脚本会输出：

- 配置说明
- 可直接执行的 `INSERT` SQL

返回给用户时，说明文字使用中文，但 SQL 保持原样。

## 脚本行为

内置脚本会：

- 从目标库读取目标表元数据
- 尽可能读取字段注释
- 从参考库查询合法参考行
- 保证多个映射字段优先取自同一条参考记录，避免字段错配
- 对非关联字段优先按“字段注释 / 字段名 / 字段类型”自动生成
- 如果用户显式提供规则，则优先使用用户规则覆盖自动策略
- 当元数据不足或合法参考值不足时直接报错，不猜测

## 当前支持的生成规则类型

当前脚本支持：

- `fixed`
- `sequence`
- `enum`
- `decimal_range`
- `int_range`
- `datetime`
- `uuid`
- `null`

示例：

```json
"order_id": {
  "type": "sequence",
  "prefix": "ORD20260514",
  "start": 1,
  "width": 3
}
```

如果用户要求的规则类型当前还不支持，要么扩展脚本，要么明确说明当前 skill 版本无法安全保证。

即使用户没有提供任何非关联字段规则，只要表结构和字段注释足够明确，也应优先尝试自动生成。

## 停止条件与安全要求

遇到以下情况时停止生成，并要求补充信息：

- 目标数据库类型当前不支持
- 字段映射关系不清晰
- 实时参考查询返回的合法数据少于要求条数
- 严格正确性依赖当前脚本尚未读取到的约束信息
- 用户要求多参考表 join，但未提供关联逻辑

不要输出“看起来完整、实际上不可靠”的 SQL。

## 输出契约

最终输出必须严格保留两段结构。

### 1. 配置说明

至少包含：

- 目标库表
- 实际插入字段
- 参考库表
- 参考过滤条件
- 字段映射关系
- 生成条数
- 插入模式
- 自动生成策略或用户覆盖规则
- 约束说明

### 2. 可直接执行的 INSERT SQL

要求：

- SQL 必须可以直接执行
- 关联字段值必须可追溯到参考查询结果
- SQL 代码块中不要混入解释性文字

## 资源文件

### scripts/

- [generate_test_data_sql.py](scripts/generate_test_data_sql.py)：连接实时数据库、读取元数据、查询合法参考值并生成最终 `INSERT` SQL

### references/

- [config-template.json](references/config-template.json)：可直接执行的最小 JSON 配置模板
- [config-template.example.json](references/config-template.example.json)：更直观的示例配置
- [input-template.md](references/input-template.md)：当用户提供的信息不完整时使用的补充输入模板
