---
name: verify-api-migration-result
description: 执行 API 驱动的数据迁移结果核验。适用于迁移已执行完成，需要检查源基线、目标数据库、目标开放接口、对象存储、文件、ID 映射、主数据、关系数据是否正确的场景。这个 Skill 负责核验逻辑、差异识别、字段覆盖分析、只读证据收集和结构化结果产出，不负责最终主报告排版；执行迁移测试时默认在结构化结果产出后继续调用 `generate-api-migration-report` 生成 HTML 报告，并在 JSON 中标记 `chain_type=direct|staged`；只有用户明确说不需要测试包报告、不生成报告或不生成 HTML 时才跳过。
---

# API 迁移结果核验

本 Skill 负责“核验”，不负责“最终主报告排版”。

职责边界：

- 负责：查库、读接口、核对对象存储或文件、识别差异、分析字段覆盖、给出结论、产出结构化核验结果。
- 不负责：把核验结果排版成统一的中文 HTML 主报告。

执行 API 迁移核验或迁移测试时，本 Skill 默认先完成核验并产出结构化结果，再交给 `generate-api-migration-report` 生成正式中文 HTML 报告，不等待用户额外指出“需要报告”：

- 直连迁移：`源接口/源库/源文件 -> 目标库/目标接口/目标文件`，结构化结果标记 `chain_type=direct`。
- 分阶段迁移：`源/第三方接口 -> 中间层 -> 目标层`，结构化结果标记 `chain_type=staged`。

只有用户在本次需求中明确说明“不需要测试包报告”“不生成报告”“不生成 HTML”或等价否定时，才跳过 HTML 报告，并在最终回复说明跳过原因。

`reporting.default_generate_report` 仅作为历史配置或项目偏好记录；对迁移测试不再作为跳过报告的依据。若配置为 `false` 但用户未明确拒绝报告，仍必须生成 HTML 报告。

## 适用范围

适用于以下场景：

- 源基线与目标系统结果数据的准确性核验。
- API 导入后的目标数据库、目标开放接口、对象存储和文件结果核验。
- 组织、账号、分类、标签、状态、素材、成片、文件、关系数据核验。
- 需要输出可复用的结构化核验结果，供后续报告或复盘使用。

不要用于以下场景：

- 纯数据库到数据库同步核验：使用 `verify-db-sync-result`。
- 已经完成核验，只需要整理 API 迁移中文 HTML 报告：使用 `generate-api-migration-report`。
- JSON/source_json 入订单主表和明细表核验：使用 `verify-json-order-ingestion`。

## 强制确认项

在给出最终通过/不通过结论前，必须先和用户确认数值比较口径：

`金额字段是否允许四舍五入？如果允许，请告知保留几位小数；比率字段是否也按同样规则处理？`

如果用户尚未确认，可以先做结构探查、准备 SQL、收集证据，但不要给最终通过/不通过结论。

## 核验流程

按以下顺序执行，不要跳步：

1. 读取迁移范围和接口文档。
2. 确认源基线来源：源库、CSV、Excel、JSON、SQL 导出或混合基线。
3. 确认目标核验来源：目标数据库、目标开放接口、对象存储、文件 URL、页面抽样。
4. 确认业务键和源到目标映射策略。
5. 读取源结构和目标结构。
6. 若源基线来自实时接口，必须先输出“源接口实际返回字段清单”，并按以下三类归类：`已纳入字段赋值/准确性规则`、`明确标记为 N/A 的字段`、`尚未纳入任何规则的字段`。
7. 建立字段映射：用户规则优先，其次字段注释语义，再其次字段名。
8. 核验总量。
9. 核验唯一性和重复数据。
10. 按业务键逐条核验字段值。
11. 核验关系数据：父子关系、归属关系、绑定关系、素材引用关系等。
12. 核验文件结果：URL、对象存储、大小、时长、封面、原文件、转码文件。
13. 汇总差异并分析可能根因。
14. 产出结构化核验结果。
15. 结构化结果产出后，默认继续调用 `generate-api-migration-report` 生成正式中文 HTML 报告，并在 JSON 中写明 `chain_type=direct|staged`。只有用户明确要求不需要测试包报告、不生成报告或不生成 HTML 时才跳过。

## 源接口字段盘点要求

当源基线来自第三方或旧系统实时接口时，必须同步记录本次实际请求参数证据，不能只记录响应字段和命中数量。

请求参数证据至少包括：
1. 接口路径和请求方法。
2. 关键业务过滤参数，例如 `videoType`、`isInner`、`sourceCode`、`contentCode`、`startTime/endTime`、`uploadStartTime/uploadEndTime`、`videoIds` 等。
3. 分批策略，例如批大小、批次数、是否存在重试、重试时哪些参数发生变化。
4. 对敏感参数脱敏，例如 token、cookie、account-key、secret；业务过滤参数不应省略。
5. 如果报告中出现“接口未返回 N 条”“live 覆盖不足”“源接口当前无记录”等结论，必须能在结构化结果里追溯到实际请求参数，避免因为缺少过滤条件说明而误判。

结构化结果中优先写入 `source_baseline.request_parameter_summary` 或各接口明细的 `request_parameters`；如果存在请求批次样例，样例中也应保留非敏感的关键过滤参数。

当源基线来自实时接口时，不能只挑当前结论需要的字段做采集，必须先做源接口字段盘点。

至少执行以下动作：

1. 先读取接口文档、用户截图或迁移设计中的“预期字段清单”，再记录源接口实际返回字段集合；若是嵌套结构，记录当前核验对象所在层级的字段集合。
2. 对每个源字段给出归类：
   - 已纳入字段赋值/准确性规则
   - 明确标记为 `N/A`
   - 尚未纳入任何规则
3. 对每个目标字段同时记录 `预期赋值规则` 和 `实际核验规则`：预期规则只能来自接口文档、迁移设计、数据库字段语义或用户确认；实际核验规则必须如实说明脚本使用了 live 响应、中间层快照、映射表还是目标库反查。
4. 若实际响应或中间层快照出现接口文档未列字段，例如脚本解析到额外嵌套数组或扩展对象，不得把该字段直接写成预期赋值规则；只能归为 `实际响应独有字段`、`中间层独有字段` 或 `待确认规则依据`，相关目标字段状态至少标记为 `WARN`，关键字段缺少规则依据时标记为 `BLOCKED`。
5. 若某字段在脚本采集阶段被丢弃，也必须在结构化结果里写明“源接口存在但本次脚本未采集的字段”和原因。
6. 若“尚未纳入任何规则”的字段非空，不得把该结果直接交付为正式主报告输入；必须先补规则、明确标记为 `N/A`，或显式阻塞。
7. 对 `isNative`、`type`、`isSysSync`、`isExpired`、统计字段、状态字段等容易被误判为辅助字段的源字段，必须显式给出归类，不得静默忽略。

### 预期规则与实际核验规则

当核验脚本需要使用接口文档未列字段、历史脚本假设字段或运行态才出现的字段时，结构化结果必须显式区分：

1. `documented_expected_fields`：接口文档或用户材料明确列出的字段。
2. `live_actual_fields`：实时接口本次实际返回字段。
3. `staging_snapshot_fields`：中间层快照或映射表中实际存在字段。
4. `expected_assignment_rule`：目标字段按文档/迁移设计应如何赋值。
5. `actual_validation_rule`：本次脚本实际用哪些来源和值做比对。
6. `rule_consistency_status`：`PASS` 表示预期与实际一致；`WARN` 表示存在非关键补证或实际字段超出文档；`BLOCKED` 表示关键规则依据缺失，不能给正式通过结论。

禁止把 `live_actual_fields` 或 `staging_snapshot_fields` 中出现但文档未列的字段，包装成“接口文档预期赋值规则”。如果无法从接口文档确认回复、子列表、状态、ID 等关键字段，需要在结论和报告中明确阻塞或待确认范围。

### 官方字段基线门禁

API 直连迁移核验中，源字段基线是字段对账合同，必须先独立构建并通过门禁后才能进入字段映射和正式报告。

字段来源优先级和允许用途如下：

1. `documented_expected_fields`：只能来自官方可见文档的响应字段表、用户提供的官方文档截图/导出字段清单，或用户明确确认的迁移字段合同；这是唯一可作为正式源字段基线的字段集合。
2. `schema_reference_fields`：开放平台文档系统的内部 schema、Swagger/OpenAPI 原始 schema、SDK 元数据、后端接口定义等结构化来源只能作为参考证据；若与官方可见文档不一致，差异字段必须进入 `schema_only_fields` 或 `schema_missing_fields`，不得自动进入正式源字段基线。
3. `live_actual_fields`：实时接口本次实际返回字段只能作为样本覆盖证据；文档没有但实时出现的字段必须进入 `live_extra_fields` 或待确认项，不得包装成官方字段。
4. `legacy_fallback_fields`：历史脚本、旧报告、兜底常量、人工记忆字段只能作为临时提示；没有官方可见文档或用户确认时，不得用于生成正式 PASS/WARN/FAIL 字段结论。
5. 目标库表字段、ODS/DWD 字段、字段注释只能用于目标侧字段声明和映射候选，禁止反推源接口文档字段。

字段基线构建必须满足以下硬门禁：

1. 必须在结构化结果中同时输出 `documented_expected_fields`、`live_actual_fields`；使用过内部 schema 或兜底字段时，还必须输出 `schema_reference_fields`、`legacy_fallback_fields` 及差异集合。
2. 字段准确性映射只能从 `documented_expected_fields` 出发；实时响应字段、内部 schema 字段和 ODS 字段不能扩大正式映射范围。
3. 文档字段存在但本次实时样本未返回时，标记为“样本未覆盖/未做逐值比对”，不得从字段基线删除，也不得按空值直接判定字段一致。
4. 实时响应存在但文档没有的字段，标记为“运行态额外字段/待确认”；若目标库承载了该字段，字段状态至少为 `WARN`，关键业务字段规则缺失时为 `BLOCKED`。
5. 内部 schema 存在但官方可见文档没有的字段，标记为“schema 参考字段/待确认”；未经用户确认不得进入 `documented_expected_fields`、`mapped_fields`、`source_fields_not_persisted` 或正式字段准确性 PASS/FAIL 统计。
6. 官方可见文档无法机器提取且用户未提供字段清单时，字段基线状态必须为 `BLOCKED`；可以继续做接口连通性、目标表结构和样本探查，但不得生成“正式字段覆盖通过/失败”结论。
7. 嵌套对象字段必须按迁移承载粒度建模：若 ODS 以 JSON 字段承载父对象或数组，例如 `company_list`、`collaborators`，正式字段基线应保留父字段并把子字段作为结构说明；不得把子字段拉平成顶层源字段后参与同名字段映射。

报告交付前必须自审以下历史高发问题：是否把内部 schema 字段当成官方可见文档字段、是否把实时响应额外字段当成文档字段、是否用 ODS 字段反推源字段、是否把嵌套子字段拉平成顶层字段、是否用旧兜底字段冒充字段基线。任一问题存在时，报告只能标为草稿或 BLOCKED，不能作为最终正式报告交付。

## 业务键规则

优先按以下顺序选择业务键：

1. 稳定源 ID + 迁移映射表。
2. 跨迁移保留的第三方 ID / 外部 ID。
3. 自然业务组合键。
4. 用户确认的兜底键。

素材类常见业务键示例：

- `source_video_id -> target_video_id`
- `third_id`
- `video_type + video_name + author + create_time`
- `finished_video_id + material_id + start + duration`

如果某个键本身可能不唯一，必须明确报告歧义，不能默认把它当唯一键继续核验。

业务键定义必须能在本次核验范围内唯一定位源记录与目标记录；单个业务对象 ID（例如广告账户 ID、店铺 ID、主体 ID）只有在该范围内确实唯一时才可单独作为业务键。若目标层保留多日期、多批次、快照或采集任务记录，结构化结果和报告必须区分“源对象键”和“核验匹配键”，并把日期、批次、快照时间、最新行选择规则或其他定位字段写入业务键与匹配策略；不得把对象 ID 单独写成完整业务键。

## 至少支持的核验类别

适用时至少覆盖以下类别：

- 组织数据：team、group、account、account-team/group、observer groups。
- 基础配置：视频类型/分类、标签组、标签项、分类与标签绑定、内容状态、默认合集。
- 媒体主数据：material、finished video、标题、描述、作者、团队、分组、分类、合集、标签、状态、时长、封面、文件大小、视频 URL。
- 文件数据：原文件、转码文件、封面文件、对象存储路径、重写后的目标 URL、URL 可访问性。
- 关系数据：成片引用素材、片段开始时间、时长、首片段、封面标记、轨道索引、轨道属性。

## 差异分类

至少分为以下类型：

1. 源有目标无。
2. 目标有源无。
3. 目标重复数据。
4. 字段值不一致。
5. 关系数据不一致。
6. 文件缺失或不可访问。
7. 映射歧义或未映射字段。
8. 因缺少基线/配置/权限而阻塞核验。

## 字段覆盖检查

当迁移把源接口 JSON 或源快照先落到映射表，再把选定字段写入业务表时，必须执行只读字段覆盖检查。

统一归类为：

1. `map有但未配置落业务表`
2. `仅存map字段未落业务表`
3. `业务表无map来源-NULL`
4. `业务表无map来源-默认值`
5. `业务表无map来源-空串`
6. `业务表无map来源-系统生成/混合`

字段覆盖结论用于解释字段来源，不应在没有业务要求时直接判定为迁移失败。

## 结构化输出产物

本 Skill 的标准交付物不是最终主报告，而是结构化核验结果。优先输出到：

1. `reports/details/<任务名>_api_migration_verification.json`
2. `reports/details/<任务名>_api_migration_verification.md`

其中：

- JSON 作为下游报告 skill 的标准输入。
- Markdown 作为便于人工复核的明细摘要。

### JSON 结构要求

JSON 至少包含以下顶层字段：

1. `task_meta`
2. `verification_scope`
3. `time_evidence`
4. `source_baseline`
5. `source_field_inventory`
6. `field_rule_coverage_summary`
7. `unmapped_source_fields`
8. `target_sources`
9. `business_keys`
10. `field_mapping_summary`
11. `totals_summary`
12. `uniqueness_summary`
13. `missing_in_target`
14. `extra_in_target`
15. `field_differences`
16. `relationship_differences`
17. `file_differences`
18. `field_coverage`
19. `coverage_gaps`
20. `likely_causes`
21. `conclusion`
22. `blocked_items`

如果迁移链路存在强制中间层，还必须额外包含：

1. `staging_layer`
2. `source_to_staging_summary`
3. `staging_to_target_summary`
4. `full_chain_consistency_summary`

### JSON 字段含义

- `task_meta`：任务名、时间、环境、版本、执行人、是否按舍入口径判定。
- `verification_scope`：迁移对象、核验类型、业务模块、批次范围、环境范围、时间筛选口径。
- `time_evidence`：报告生成时间、批次执行窗口、源时间字段实际范围、目标时间字段实际范围。
- `source_baseline`：源数据来源和口径说明。
- `source_field_inventory`：源接口实际返回字段、已纳入规则字段、`N/A` 字段、未采集字段和未纳入规则字段清单。
- `field_rule_coverage_summary`：源字段覆盖自检汇总，至少包含源字段总数、已纳入规则字段数、`N/A` 字段数、未采集字段数、未纳入规则字段数和是否可进入正式报告。
- `unmapped_source_fields`：尚未纳入任何规则的源字段清单；若非空，正式报告必须阻塞。
- `target_sources`：目标库、目标接口、对象存储、文件来源说明。
- `business_keys`：业务键、ID 映射策略、歧义说明。
- `field_mapping_summary`：字段映射来源和特殊映射规则。
- `totals_summary`：总量结果。
- `uniqueness_summary`：唯一性、重复数据结果。
- `missing_in_target` / `extra_in_target`：源有目标无、目标有源无差异样例。
- `field_differences`：字段差异分组结果。
- `relationship_differences`：关系差异分组结果。
- `file_differences`：文件、对象存储、URL 差异结果。
- `field_coverage`：字段覆盖总结和需关注字段。
- `coverage_gaps`：未独立核验、未全量反扫、仅能间接证明或缺少直接证据的覆盖缺口。
- `likely_causes`：已识别根因分类。
- `conclusion`：PASS/WARN/FAIL/BLOCKED 及理由。
- `blocked_items`：前置条件不足、配置不足、权限不足等阻塞项。

### 差异样例结构要求

`field_differences`、`relationship_differences`、`file_differences` 中的每条样例至少包含：

1. `business_key`
2. `source_id`
3. `staging_id`
4. `staging_evidence`
5. `target_id`
6. `difference_type`
7. `difference_field`
8. `source_value`
9. `target_value`
10. `difference_note`

字段值不一致必须保留可读样例，至少能展示“业务键、预期值、实际值”；若因脱敏不能展示原值，必须提供业务键哈希、源/目标空值状态和值哈希，并说明需补充可读证据。`blocked_items` 中每个 BLOCKED 项必须包含 `current_evidence`、`evidence` 或 `required_evidence`，说明接口路径、响应码、错误信息、授权范围、缺失配置或所需证据，不能只写阻塞数量或泛泛原因。

如果目标层存在多日期、多批次、快照或按最新行参与比对的规则，差异样例中的 `business_key` 必须写入实际核验匹配键，至少包含源对象键和目标最新记录定位字段，例如 `date`、`doris_update_time`、`doris_create_time`、`ods_batch_no`；单个 `advertiser_id`、`account_id`、`shop_id` 等对象 ID 只能作为 `source_object_key`，不能冒充完整差异定位键。

其中 `staging_evidence` 必须优先写真实中间层证据，例如：

- `extra_json.createTime=2025-06-30 16:15:07`
- `view_migration_file_task: 不存在`
- `file_task.status=PENDING`
- `job_param.uploadStartTime=2025-06-01`

不要仅用 `old_id=... -> new_id=...` 重复代替中间层证据；如果只有映射链而无直接快照或任务证据，必须明确写成“仅有映射标识，缺少中间层直接证据”。

### 覆盖缺口输出要求

若某个维度没有独立核验，不要把它塞进 `missing_in_target`、`extra_in_target` 或其他正常结果并写成 `0`。

统一写入 `coverage_gaps`，每项至少包含：

1. `gap_item`
2. `status`
3. `reason`
4. `current_evidence`
5. `impact_scope`

其中：

- `status` 只允许 `WARN` 或 `BLOCKED`
- `reason` 说明为什么没有形成独立核验
- `current_evidence` 说明当前只拿到了什么间接证据
- `impact_scope` 说明影响的是哪个判断维度

### Markdown 明细摘要要求

Markdown 明细应至少包含：

1. 核验范围
2. 关键统计
3. 关键差异分类
4. 代表样例
5. 结论
6. 阻塞项

## 源字段清单结构要求

`source_field_inventory` 至少按接口输出以下字段：

1. `interface_name`
2. `interface_path`
3. `actual_source_fields`
4. `mapped_fields`
5. `na_fields`
6. `explicitly_uncollected_fields`
7. `unmapped_fields`
8. `note`

其中：

- `actual_source_fields` 是接口实际返回字段集合。
- `mapped_fields` 是已经进入字段赋值或准确性规则的字段。
- `na_fields` 是明确说明“不参与本链路验收”的字段。
- `explicitly_uncollected_fields` 是接口返回但本次脚本未采集的字段。
- `unmapped_fields` 是既未进入规则、也未标记为 `N/A`、也未声明未采集的字段。

`field_rule_coverage_summary` 至少包含：

1. `actual_source_field_total`
2. `mapped_field_total`
3. `na_field_total`
4. `explicitly_uncollected_field_total`
5. `unmapped_field_total`
6. `gate_passed`
7. `note`

`unmapped_source_fields` 每项至少包含：

1. `interface_name`
2. `field_name`
3. `reason`
4. `current_status`
5. `suggested_action`

Markdown 是辅助明细，不替代 JSON。

## 与报告 Skill 的衔接规则

当满足以下条件时，把本 Skill 的 JSON 结果交给 `generate-api-migration-report`，并设置 `chain_type=direct`：

1. 用户未明确要求不需要测试包报告、不生成报告或不生成 HTML。
2. 迁移链路属于“源接口/源库/源文件 -> 目标库/目标接口/目标文件”的直连迁移，没有强制中间层、ODS/DWD 多跳阶段或映射表阶段需要单独展示。
3. 本 Skill 已经产出完整的结构化核验结果。

交给统一报告 Skill 时，direct 链路必须保证 JSON 中已有：

- 源基线来源和源过滤条件
- 目标来源和目标过滤条件
- 业务键与唯一性说明
- 总量、缺失、额外、重复、字段差异结果
- 字段赋值规则和字段准确性核验结果；若源基线缺失，字段准确性必须标记 `BLOCKED`
- 覆盖缺口、结论口径和阻塞项

当满足以下条件时，把本 Skill 的 JSON 结果交给 `generate-api-migration-report`，并设置 `chain_type=staged`：

1. 用户未明确要求不需要测试包报告、不生成报告或不生成 HTML。
2. 迁移链路属于“源/第三方接口 -> 中间层 -> 目标层”。
3. 本 Skill 已经产出完整的结构化核验结果。

交给统一报告 Skill 时，staged 链路必须保证 JSON 中已有：

- 三层来源说明
- 阶段一结果
- 阶段二结果
- 全链路结果
- 字段覆盖说明
- 差异样例
- 结论口径
- 阻塞项

## 文件检查规则

文件核验保持只读：

- 源文件存在时，检查目标 URL 非空。
- 有对象存储凭据时，检查对象或 URL 是否可访问。
- 源目标大小都可得时，检查文件大小。
- 有元数据时，检查视频时长。
- 原文件、转码文件、封面文件分开核验。

除非用户明确要求或抽样规则必须下载，否则不要下载大文件。

## 失败原因总结

当存在差异时，优先从以下角度归因：

- 迁移批次未完成。
- 源到目标 ID 映射错误。
- 分类、标签、状态映射错误。
- 团队、分组、账号归属映射错误。
- 文件已上传但目标 URL 未重写。
- 目标 URL 已重写但对象存储文件缺失。
- 单位换算错误，例如秒与微秒。
- 重跑后创建了重复记录。
- 被引用对象尚未迁移完成。
- 展示字段与业务字段混用。
- 精度或舍入规则不一致。

## 安全规则

- 默认只执行只读 SQL：`SELECT`、元数据查看、只读探查语句。
- 不执行 `INSERT`、`UPDATE`、`DELETE`、`TRUNCATE`、`DROP`、`ALTER` 或迁移写接口。
- 输出中必须脱敏凭据、token、cookie、密钥等敏感信息。
- 不得在报告或最终回复中输出生产密码、生产 token、生产 cookie、对象存储密钥。
- 用户提供的真实敏感配置只保留在配置文件，不得回显。

## 最终回复格式

最终回复用户时，至少提供：

1. 简短结论
2. 结构化核验结果路径（JSON，如已生成）
3. 明细摘要路径（Markdown，如已生成）
4. 是否按用户确认的金额/比率舍入口径判定
5. 是否存在必须研发修复的问题
6. 已交给 `generate-api-migration-report` 生成最终 HTML 报告，并说明 `chain_type`；若用户明确要求不需要测试包报告、不生成报告或不生成 HTML，则说明跳过原因
7. 因缺少基线、映射、数据库配置、接口配置、对象存储配置导致的阻塞项

## 参考资料

当需求涉及云视频管家、素材、成片、MinIO、视频导入、成片引用素材时，读取 `references/cloud-video-manager.md`。
