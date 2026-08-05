# AGENT_RULES.md

本文件为当前项目测试任务的最高入口规则。每次处理本项目测试相关任务前，必须先读取 `AGENTS.md` 和本文件，再按“知识与规则加载索引”读取必要的拆分文档。

`AGENT_RULES.md` 只保留 P0/P1 门禁、执行流程和文档索引；详细文件管理、报告门禁、自动化治理、历史反馈和业务知识写入 `docs/`。

## P0 测试交付硬门禁

- 正式测试结论必须来自真实请求、真实核验结果或明确标记的阻塞状态；未执行不得包装成完成报告。
- 已沉淀测试矩阵、用例基线或自动化资产时，复测、回归和正式执行必须优先复用基线；缩小范围必须由用户明确要求，并在报告结论中说明未覆盖项。
- 生成或更新测试报告后，必须读取最终 HTML/Markdown/JSON/报告索引产物完成自审；自审不通过不得标记为最终交付。
- `reports/current.md` 固定只维护版本级当前有效结论，一个版本一条记录，不展开接口、模块、小点或批次明细。
- 正式报告包只能进入 `reports/final/`；目录名必须使用 ASCII slug，中文标题写入包内 `README.md` 和 `manifest.yaml`。
- 正式报告包必须声明 `artifact_policy`，并通过报告包门禁、链接检查、体积上限、UTF-8、脱敏和证据归档检查。
- 普通执行流水、临时诊断、rerun、完整 JSON 证据、截图、日志和运行缓存默认进入 `work/versions/<VERSION-ID>/runs/<RUN-ID>/`，不进入 Git。
- 本地真实配置、真实 token/cookie/密码/连接串不得写入规则、报告、日志、Git 或最终回复。
- 生产写入、不可回滚 SQL、生产压测、绕过鉴权、真实凭据暴露、强制推送、重置历史等高风险动作必须先阻止并等待明确授权。

## 项目信息

- 项目名称：<PROJECT_NAME>
- 项目类型：<WEB/API/DATA/OTHER>
- 业务范围：<PROJECT_BUSINESS_SCOPE>
- 主要使用方：<USER_ROLE_OR_TEAM>
- 项目入口文件：`AGENTS.md`
- 项目测试规则入口：`AGENT_RULES.md`
- 规则与知识索引：`docs/README.md`
- 当前结论入口：`reports/current.md`

## 必读顺序

1. 读取 `AGENTS.md`，确认本项目测试任务默认使用 `$senior-test-engineer-agent`。
2. 读取 `AGENT_RULES.md`，确认 P0/P1 门禁和知识加载索引。
3. 从用户请求和当前任务材料中识别任务对象、执行动作、产物目标、版本范围、风险域。
4. 按“知识与规则加载索引”读取 `docs/rules/` 或 `docs/knowledge/` 中的必要文档。
5. 读取环境变量、`config/test-agent.config.local.json` 和 `config/test-agent.config.example.json`。
6. 若任务依赖数据库、对象存储、外部接口或真实账号，但配置缺失或只存在占位符，先暂停业务执行并补齐配置。

## 知识与规则加载索引

执行时不允许默认加载全部 `docs/`。必须先识别以下判定维度，再按索引表加载对应文档；执行中发现跨域时再补读对应文档。

判定维度：

- 任务对象：接口、页面、数据库、报告、自动化脚本、版本目录、Git、配置、测试数据等。
- 执行动作：设计、执行、复测、回归、重建、归档、提交、推送、清理、修复等。
- 产物目标：测试点、测试用例、矩阵、报告、证据、SQL、executor、suite、正式报告包、当前结论入口等。
- 版本范围：当前版本、临时批次、历史执行批次、作废范围等。
- 风险域：敏感配置、生产/预发只读、权限边界、数据一致性、加解密链路、历史反馈防再犯等。

| 索引匹配条件 | 必读文档 |
| --- | --- |
| 目录、`work/versions`、`RUN-*`、Git 纳管、`reports/current.md`、`reports/final`、配置忽略 | `docs/rules/file-management.md` |
| 报告生成、正式报告、详情归属、自审、报告包门禁、体积上限、证据归档 | `docs/rules/reporting-gate.md` |
| executor、suite、自动化资产、执行前门禁、报告生成器、依赖管理 | `docs/rules/automation-governance.md` |
| 用户历史反馈、重复问题防再犯、目录或报告样式退化 | `docs/rules/history-regression-guards.md` |
| 项目业务事实、接口口径、环境事实、字段映射、数据一致性规则 | `docs/knowledge/README.md` 及其中匹配文档 |

## 默认执行清单

- 完成需求有效性审查：目标、范围、版本、输入材料、验收标准、环境配置、权限边界和数据边界必须清晰。
- 识别任务类型和适用专项 Skill。
- 按加载索引读取必要规则或知识文档。
- 明确输入材料、测试范围、输出产物路径。
- 执行测试设计、脚本编写、SQL 校验、接口执行或报告生成。
- 主动识别优化点，并说明依据、原因、收益、落地方式、优先级和是否建议本次执行。
- 执行自检：格式、路径、脱敏、覆盖范围、可执行性和门禁结果。
- 输出结论、产物路径、验证结果、风险和优化建议。

## 文件与报告纳管摘要

- 新增测试、复测、核验、诊断、报告重建必须先进入 `work/versions/<VERSION-ID>/runs/<RUN-ID>/`。
- 版本号类工作区使用 `work/versions/VERSION-<主版本>-<次版本>-<修订版本>/`，例如 `VERSION-1-1-1`。
- 同一用户任务覆盖多个接口或多个测试项时，只能创建一个共享 `RUN-*`，除非不同接口分属不同环境、时间窗口或用户明确要求拆分。
- 单次 `RUN-*` 批次入口固定为 `reports/index.md` 和 `reports/index.html`。
- `reports/current.md` 只维护版本级当前有效结论，固定一个版本一条记录。
- `reports/final/` 只保存已确认长期纳管的正式报告包。
- 正式报告包目录名必须使用 ASCII slug，格式建议为 `<version>_<suite-or-module>_<scope>_final_report`。
- 单个正式报告包 Git 纳管软上限为 10 MB，硬上限为 20 MB；单文件软上限为 2 MB，硬上限为 5 MB；`evidence/` 下 JSON 合计软上限为 3 MB，硬上限为 8 MB。

## 配置与敏感信息摘要

- 配置读取顺序：环境变量 → `config/test-agent.config.local.json` → `config/test-agent.config.example.json` → 向用户确认。
- `config/test-agent.config.example.json` 只能保存占位符和示例结构，可以提交。
- `config/*agent.config.local.json` 和 `config/test.json` 保存本地真实配置，必须加入 `.gitignore`，不得提交。
- 预发和正式环境默认按只读处理；未明确允许时禁止写入和压测。
- 输出日志、SQL、报告时必须对账号、手机号、token、cookie、密钥、连接串做脱敏处理。

## 专项 Skill 调度规则

- 命中专项 Skill 场景时，优先按插件内置 Skill 执行；只有插件内置 Skill 缺失或损坏时，才回退到全局同名 Skill，并在最终结果中说明原因。
- 首次生成或更新接口测试点、测试用例、断言策略时，调用 `api-test-design`。
- 已有接口矩阵的执行、复测或回归，优先复用矩阵；Linker/OpenAPI/直连网关/加密请求场景调用 `linker-gateway-api-test`。
- 数据库到数据库同步结果核验调用 `verify-db-sync-result`。
- API 迁移核验调用 `verify-api-migration-result`；需要最终 HTML 报告时再调用 `generate-api-migration-report`。
- JSON/source_json 入库核验调用 `verify-json-order-ingestion`。
- UI 自动化定位、页面运行态采集、定位候选、稳定性校验和资产沉淀按对应 UI 自动化 Skill 调度。
- 蓝湖、HTML 原型、截图或结构化需求生成测试点/用例时，按需求提取、对象分析、测试点和用例生成链路调用对应 Skill。

## 规则维护

- 新增强制门禁、跨任务通用规则或会影响所有执行流程的约束，写入 `AGENT_RULES.md`。
- 新增文件管理、报告、自动化、历史反馈防再犯规则，优先写入 `docs/rules/`。
- 新增已验证业务事实、环境事实、数据映射、版本口径，优先写入 `docs/knowledge/`。
- 不得把未经验证的猜测、临时判断、真实凭据或敏感配置写入任何规则或知识文档。
- 若拆分文档与本文件冲突，以本文件 P0/P1 门禁为准。
