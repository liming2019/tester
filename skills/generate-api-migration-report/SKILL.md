---
name: generate-api-migration-report
description: 基于已完成的 API 驱动数据迁移核验结果，统一生成中文 HTML 报告和结构化 JSON 明细。适用于 verify-api-migration-result 已产出核验结构化结果后，需要按同一套主报告样式输出报告的场景；同时支持 direct 直连链路（源/接口/文件到目标库/接口/文件）和 staged 分阶段链路（两阶段、三阶段或源/第三方接口到中间层/映射层再到目标层）。单接口直接输出明细报告，多接口输出主报告和分接口明细页。
---

# API 迁移报告生成

本 Skill 是 API 迁移核验报告的统一入口，负责把已有核验结果整理成正式交付物，不负责重新查库、调接口或补业务规则。

## 职责边界

负责：

- 读取 `verify-api-migration-result` 或人工整理后的结构化 JSON。
- 根据 `chain_type` 区分 `direct` 和 `staged`；未提供时按是否存在中间层字段自动推断。
- 统一主报告样式、单接口/多接口输出策略、状态口径、章节校验和 UTF-8 自检。
- 按链路类型生成明细页：direct 展示“源到目标”，staged 展示“源到中间层 / 中间层到目标”。
- 输出 HTML 与结构化 JSON 明细，并保证敏感信息不在报告正文中明文扩散。

不负责：

- 执行迁移核验。
- 把 direct 链路伪装成 staged，或把 staged 中间层证据合并成 direct。
- 在缺少源基线、目标来源、业务键、字段规则或关键证据时强行写 `PASS`。

## 交付分层

- `draft`
  仅输出结构化 JSON 和阻塞说明。只在用户明确要求草稿，或关键输入不足且总体状态为 `BLOCKED` 时使用。
- `standard`
  单接口默认模式。输出单接口明细 HTML + JSON，不生成主报告、不生成分接口目录。
- `full`
  多接口默认模式。输出主 HTML + JSON + 分接口 HTML 明细页。

## 主报告固定结构

只有多个接口时才输出主报告。主报告顶部摘要卡片展示总体结论、测试接口数、通过接口数、阻塞接口数、失败接口数，不在正文重复渲染“执行结果概述”章节。主报告正文固定 2 段：

1. 核验明细
   展示接口名称、核验接口路径、核验范围、核验规则、核验环境、核验状态、查看明细。
2. 核验结论概述
   一个接口一块，块内展示接口名称、核验接口路径、核验结果概述；不要用项目符号列表。

主报告只做摘要、统计、结论和导航；字段明细、差异样例、源/目标证据和中间层证据必须放到单接口明细或分接口明细页。
主报告不渲染目录块，避免摘要页出现重复导航；单接口明细页和分接口明细页保留目录，并默认放在正文左侧作为章节导航，窄屏下可折回正文上方。
单接口明细页和分接口明细页必须只展示当前接口的数据；`source_to_staging_summary`、`staging_to_target_summary`、`full_chain_consistency_summary`、`conclusion`、差异样例、覆盖缺口和字段规则都必须按当前接口过滤，不得混入其他接口或主报告全局结论。
分阶段明细页的“源到中间层核验结果”和“中间层到目标核验结果”是阶段摘要，不得再渲染为“接口名称 / 状态 / 详情”明细表；必须直接展示核验数据源、目标对象或目标表、核验总条数、阶段状态，不重复展示“核验结果”和“总结”行。
分阶段明细页不单独渲染“总体判定依据”章节；全链路判断应沉淀到接口概况、阶段摘要、差异样例和接口结论中，避免页面重复堆叠。
“目标数据库赋值规则及核验结果”中的“表字段”展示目标表技术字段名，“字段名”必须优先展示 `field_meaning`、目标字段中文含义或别名；不得在有中文字段含义时回退展示完整技术字段路径。该表必须使用稳定列宽：表字段/字段名列不抢占过多宽度，检查记录数/不匹配记录数/状态列必须留出清晰宽度，长规则列允许横向滚动兜底。
报告表格行 hover 背景色必须与默认底色和隔行底色明显区分，优先使用温和高亮色，不使用相近浅蓝导致用户难以定位当前行。

## 明细页分支

`direct` 明细页固定章节：

1. 接口概况
2. 源接口字段盘点与归类
3. 目标数据库赋值规则及核验结果
4. 源到目标核验结果
5. 完整性与唯一性核验结果
6. 接口字段未入库说明
7. 覆盖缺口与不适用说明
8. 差异样例
9. 接口结论

`staged` 明细页固定章节：

1. 接口概况
2. 源接口字段盘点与归类
3. 目标数据库赋值规则及核验结果
4. 覆盖缺口与不适用说明
5. 源到中间层核验结果
6. 中间层到目标核验结果
7. 差异样例
8. 接口结论

## 输入约定

优先使用 `chain_type`：

- `direct`：源到目标直连链路，没有必须展示的中间层快照、映射层或批次层。
- `staged`：两阶段、三阶段或源到中间层/映射层再到目标层的分阶段链路，中间层或映射层证据是核验结论的一部分。

未提供 `chain_type` 时：

- 只要存在 `staging_layer`、`source_to_staging_summary`、`staging_to_target_summary` 或 `full_chain_consistency_summary`，推断为 `staged`。
- 否则推断为 `direct`。

共同关键输入：

- `verification_scope`
- `source_baseline`
- `target_sources` 或 `target_source`
- `business_keys`
- `conclusion`

`direct` 额外优先输入：

- `totals_summary`
- `uniqueness_summary`
- `field_assignment_rules` 或 `field_mapping_summary`
- `field_accuracy_summary` 或 `field_accuracy_details`
- `source_fields_not_persisted`
- `missing_in_target`
- `extra_in_target`
- `duplicate_in_target`
- `field_differences`
- `coverage_gaps`

`staged` 额外关键输入：

- `staging_layer`
- `source_to_staging_summary`
- `staging_to_target_summary`
- `full_chain_consistency_summary`

字段级章节优先读取：

- `source_field_inventory`
- `field_rule_coverage_summary`
- `unmapped_source_fields`
- `interface_inventory`
- `field_assignment_rules`
- `field_accuracy_summary`
- `field_accuracy_details`
- `coverage_gaps`

## 固定执行流程

1. 先把上游结果整理成 canonical JSON；不要直接在自由文本上拼报告。
2. 运行 `scripts/validate_api_migration_report.py input` 校验输入契约。
3. 运行 `scripts/render_api_migration_report.py` 生成 HTML 和 JSON。
4. 运行 `scripts/validate_api_migration_report.py output` 校验章节、分层、UTF-8 和版式。
5. 若是项目正式报告，按项目规则更新 `reports/index.md`。

## 兼容策略

- 新任务默认使用本 Skill。
- `generate-direct-api-migration-report` 和 `generate-staged-api-migration-report` 暂时保留为历史兼容入口，不立刻删除。
- 旧入口后续只应作为薄入口或迁移说明；公共主报告样式和后续规则变更以本 Skill 为准。

## 资源

- `assets/report_contract.json`：统一输入/输出契约。
- `assets/report_template.html`：主报告和明细页共用模板。
- `scripts/render_api_migration_report.py`：统一 HTML/JSON 生成脚本。
- `scripts/validate_api_migration_report.py`：统一输入/输出校验脚本。
- `references/api-migration-report-checklist.md`：边界场景和人工补写检查清单。

## 最终回复用户

至少输出：

1. 简短结论。
2. 使用的 `chain_type` 和交付模式。
3. 正式 HTML 路径；单接口说明为明细报告，多接口说明为主报告。
4. 结构化 JSON 明细路径。
5. 分接口 HTML 目录；单接口说明未生成目录的原因。
6. 校验结果和剩余风险。
