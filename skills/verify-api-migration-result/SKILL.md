---
name: verify-api-migration-result
description: 执行 API 驱动的数据迁移结果核验。适用于迁移已执行完成，需要检查源基线、目标数据库、目标开放接口、对象存储、文件、ID 映射、主数据、关系数据是否正确的场景。这个 Skill 负责核验逻辑、差异识别、字段覆盖分析、只读证据收集和结构化结果产出，不负责最终主报告排版；若用户还要求把核验结果整理成统一中文 HTML 报告，且链路属于“源到中间层再到目标层”的两阶段迁移，则将结构化结果交给 `generate-staged-api-migration-report`。
---

# API 迁移结果核验

本 Skill 负责“核验”，不负责“最终主报告排版”。

职责边界：

- 负责：查库、读接口、核对对象存储或文件、识别差异、分析字段覆盖、给出结论、产出结构化核验结果。
- 不负责：把核验结果排版成统一的中文 HTML 主报告。

如果用户同时要求“执行核验 + 生成最终统一报告”，并且迁移链路是“源/第三方接口 -> 中间层 -> 目标层”，则本 Skill 先完成核验并产出结构化结果，再交由 `generate-staged-api-migration-report` 生成主报告。

在读取项目配置时，额外读取 `reporting.default_generate_report`：

- 若为 `true`，则核验任务默认需要继续输出报告，除非用户明确要求“不生成报告”。
- 若为 `false`，则只输出结构化核验结果，除非用户明确要求“生成报告”。

## 适用范围

适用于以下场景：

- 源基线与目标系统结果数据的准确性核验。
- API 导入后的目标数据库、目标开放接口、对象存储和文件结果核验。
- 组织、账号、分类、标签、状态、素材、成片、文件、关系数据核验。
- 需要输出可复用的结构化核验结果，供后续报告或复盘使用。

不要用于以下场景：

- 纯数据库到数据库同步核验：使用 `verify-db-sync-result`。
- 已经完成核验，只需要整理最终两阶段迁移中文报告：使用 `generate-staged-api-migration-report`。
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
6. 建立字段映射：用户规则优先，其次字段注释语义，再其次字段名。
7. 核验总量。
8. 核验唯一性和重复数据。
9. 按业务键逐条核验字段值。
10. 核验关系数据：父子关系、归属关系、绑定关系、素材引用关系等。
11. 核验文件结果：URL、对象存储、大小、时长、封面、原文件、转码文件。
12. 汇总差异并分析可能根因。
13. 产出结构化核验结果。
14. 如果用户要求最终统一报告，或配置 `reporting.default_generate_report=true`，且链路属于两阶段迁移，则把结构化结果交给 `generate-staged-api-migration-report`。

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
5. `target_sources`
6. `business_keys`
7. `field_mapping_summary`
8. `totals_summary`
9. `uniqueness_summary`
10. `missing_in_target`
11. `extra_in_target`
12. `field_differences`
13. `relationship_differences`
14. `file_differences`
15. `field_coverage`
16. `coverage_gaps`
17. `likely_causes`
18. `conclusion`
19. `blocked_items`

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

Markdown 是辅助明细，不替代 JSON。

## 与报告 Skill 的衔接规则

当满足以下条件时，把本 Skill 的 JSON 结果交给 `generate-staged-api-migration-report`：

1. 用户明确要求最终统一中文 HTML 报告。
2. 迁移链路属于“源/第三方接口 -> 中间层 -> 目标层”。
3. 本 Skill 已经产出完整的结构化核验结果。

交给报告 Skill 时，必须保证 JSON 中已有：

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
6. 是否还需要交给 `generate-staged-api-migration-report` 生成最终 HTML 报告
7. 因缺少基线、映射、数据库配置、接口配置、对象存储配置导致的阻塞项

## 参考资料

当需求涉及云视频管家、素材、成片、MinIO、视频导入、成片引用素材时，读取 `references/cloud-video-manager.md`。
