# AGENT_RULES.md

本文件为当前项目的测试 Agent 项目级规则。资深测试工程师 Agent 每次处理本项目任务前必须先读取本文件，并将其作为项目级最高测试准则。

项目根目录 `AGENTS.md` 用于声明本项目测试任务默认使用 `$senior-test-engineer-agent`；本文件用于保存项目级测试准则、业务规则和执行约束。

## 项目信息

- 项目名称：<PROJECT_NAME>
- 项目类型：<WEB/API/DATA/OTHER>
- 业务范围：<PROJECT_BUSINESS_SCOPE>
- 主要使用方：<USER_ROLE_OR_TEAM>
- 项目入口文件：`AGENTS.md`
- 项目测试规则文件：`AGENT_RULES.md`

## 测试环境

- 测试环境地址：<TEST_BASE_URL>
- 预发环境地址：<PRE_BASE_URL>
- 生产环境地址：<PROD_BASE_URL>
- 登录账号：<TEST_ACCOUNT>
- 敏感信息说明：禁止在本文件记录真实密码、token、cookie、生产库连接串。
- 本地配置文件：`config/test-agent.config.local.json`
- 配置模板文件：`config/test-agent.config.example.json`
- 配置策略：`test-agent.config.example.json` 保存全量参考结构；`test-agent.config.local.json` 保存本地最小可用配置。
- 当前环境选择：环境变量 `TEST_AGENT_ENV` 或 `APP_ENV` → `active_environment` → `local.environments` 中唯一已配置环境 → 用户明确指定环境

## 测试范围

- 功能测试范围：<FUNCTION_SCOPE>
- 接口测试范围：<API_SCOPE>
- 自动化测试范围：<AUTOMATION_SCOPE>
- 性能测试范围：<PERFORMANCE_SCOPE>
- 数据库校验范围：<DATABASE_SCOPE>

## 原型与需求规则

- 原型来源：<LANHU_OR_PRD_URL>
- 需求版本：<VERSION>
- 测试点提取必须严格基于原型可见内容、需求文档和 Notes 标注，不允许脑补。
- 默认覆盖正常、边界、异常、兼容、权限、数据一致性和回归影响范围。

## 接口规则

- 接口文档地址：<API_DOC_URL>
- 鉴权方式：<AUTH_METHOD>
- 公共请求头：<COMMON_HEADERS>
- 接口测试必须覆盖正常参数、缺失参数、非法参数、边界参数、权限不足、登录失效、重复提交、幂等性。

## 数据库规则

- 数据库类型：<DB_TYPE>
- 数据库连接配置来源：<DB_CONFIG_PATH>
- 只读校验优先，不得直接修改数据。
- 涉及数据修改 SQL 时，必须提供备份 SQL、执行 SQL、回滚 SQL、影响范围和验证 SQL。

## 自动化测试规则

- 默认框架：Playwright Python
- 脚本执行目录：专属 Git Worktree
- 元素定位优先级：data-testid > role/name > label > text > CSS/XPath
- 自动化脚本交付前必须完成真实运行；环境不具备时，至少完成语法检查、依赖检查、定位策略检查和逻辑自测。

## 性能测试规则

- 性能测试对象：<PERFORMANCE_TARGET>
- 并发模型：<CONCURRENCY_MODEL>
- 关键指标：响应时间、吞吐量、错误率、资源占用、业务成功率。
- 性能测试必须说明压测数据、压测入口、风险控制和回滚/停止条件。

## 输出规则

- 创建或初始化项目后，必须在最终回复中输出项目根目录绝对路径。
- 测试点默认生成真实 `.xmind` 文件。
- `.xmind` 生成失败时，自动降级为支持一键导入 XMind 的 Markdown 结构，并说明失败原因和产物路径。
- 测试报告主报告只展示摘要、统计、结论和风险；执行明细、缺陷明细、接口明细、性能明细、SQL 校验明细独立输出。
- 每次生成测试报告后，必须更新 `reports/index.md`。

## 需求有效性审查规则

- 每次执行测试任务前，必须先检查任务目标、测试范围、需求版本、输入材料、验收标准、环境配置、权限边界、数据边界是否清晰。
- 若需求不合法、不清晰或不可执行，必须明确指出问题点、为什么会影响测试结果或交付质量、需要补充的信息、可先执行的低风险事项。
- 若需求只影响部分范围，必须拆分为“可立即执行部分”和“需确认后执行部分”，先推进可执行部分。
- 不得脑补业务规则、接口参数、数据库关系、权限边界或验收标准。
- 对生产写入、不可回滚 SQL、生产压测、绕过鉴权、真实凭据暴露等高风险要求，必须先拦截并给出安全替代方案。

## 主动优化建议规则

- 每次执行测试任务时，必须主动识别与当前任务相关的潜在优化点。
- 每条优化建议必须包含：发现依据、为什么要做、预期收益、落地方式、优先级、是否建议本次执行。
- 优化方向优先覆盖：测试覆盖缺口、边界遗漏、测试数据构造、自动化可维护性、SQL 回滚与审计、接口幂等与权限校验、报告结构、环境隔离、配置脱敏、缺陷复测效率。
- 若优化建议会扩大任务范围，必须标记为后续优化并等待用户确认，不得擅自扩大交付范围。
- 已验证且适合长期复用的优化点，必须追加到本文件对应章节。

## 项目目录规范

- `inputs`：存放原型截图、PRD、接口文档、数据库结构、日志等输入材料。
- `work`：存放中间产物、临时脚本、草稿和过程分析文件。
- `testpoints`：存放测试点 XMind、可导入 XMind 的 Markdown 降级文件。
- `testcases`：存放测试用例 Markdown、Excel、执行记录。
- `automation`：存放 Playwright Python、Katalon Studio Groovy 等自动化测试脚本。
- `automation/playwright`：存放 Playwright Python 自动化脚本和配置。
- `sql`：存放查询 SQL、校验 SQL、备份 SQL、回滚 SQL 和数据库核验脚本。
- `data`：存放测试数据、构造数据、脱敏样本和导入导出文件。
- `reports`：存放测试主报告和报告索引。
- `reports/details`：存放测试用例执行明细、缺陷明细、接口明细、性能明细、SQL 校验明细。
- `outputs`：存放最终交付物、测试报告和可直接评审的结果文件。
- 后续执行本项目任务时，除用户另有指定，产物必须优先写入项目根目录下对应分类目录。

## 项目配置读取规则

- 配置读取顺序：环境变量 → `config/test-agent.config.local.json` → `config/test-agent.config.example.json` → 向用户确认。
- `test-agent.config.example.json` 保存全量参考结构，可包含 `schema_version`、`active_environment`、`environment_order`、`dev/test/pre/prod`、对象存储、性能配置和安全策略。
- `test-agent.config.local.json` 保存本地实际使用配置，允许采用最小结构；只需要配置当前任务会用到的环境、账号、数据库、对象存储或路径，不强制保留所有环境和所有字段。
- `reporting.default_generate_report=true` 表示核验任务默认继续输出报告；仅当用户明确要求“不生成报告”时才跳过。
- 当前环境读取顺序：环境变量 `TEST_AGENT_ENV` 或 `APP_ENV` → `active_environment` → `local.environments` 中唯一已配置环境 → 用户明确指定环境 → 向用户确认。
- 读取某环境配置时，只读取 `environments.<env>` 下已配置的 `base_url`、`accounts`、`databases`、`object_storages`、`safety`，不得混用其他环境配置。
- 数据库默认读取 `environments.<env>.databases.primary`；若任务明确指定业务库、日志库、报表库等别名，则读取对应别名。
- 若某任务需要的配置字段在 `local` 中不存在，先查看 `example` 的字段位置，再向用户确认并补齐 `local`，不得擅自编造。
- 预发和正式环境默认按只读处理；若 `safety.allow_write_sql=false` 或数据库 `read_only=true`，禁止输出直接执行的数据修改 SQL，只能输出只读核验 SQL 或需审批的方案。
- 性能测试必须读取当前环境 `safety.allow_performance_test`；若未配置该字段且环境为 `pre` 或 `prod`，默认禁止压测；若环境为 `dev` 或 `test`，仍需用户确认压测范围和停止条件。
- `test-agent.config.example.json` 只能保存占位符和示例结构，可以提交。
- `test-agent.config.local.json` 保存本地真实配置，必须加入 `.gitignore`，不得提交。
- 禁止把真实 token、cookie、密码、生产库连接串写入 `AGENT_RULES.md`、报告或最终回复。
- 最终回复涉及敏感配置时必须脱敏，例如只显示 `<TOKEN>`、`***` 或末尾 4 位。

## 专项 Skill 调度规则

- 蓝湖链接、蓝湖版本、蓝湖需求提取、蓝湖测试点或测试用例：调用 `lanhu-to-testcase`。
- 仅提取蓝湖结构化需求：调用 `lanhu-requirements-extractor`。
- 已有结构化需求或截图/需求材料生成测试点：调用 `extract-functional-test-points`。
- 需要编排一整条 UI 自动化定位链路，把任务拆成运行态采集、组件识别、候选定位、稳定性校验和资产沉淀时：调用 `ui-locator-orchestrator`。
- 用户提供页面 URL、登录态或交互步骤，需要采集真实运行态 DOM、截图、a11y 或状态快照时：调用 `capture-web-runtime`。
- 已有运行态材料，需要识别筛选区、工具栏、表格、分页、弹窗、树或页签等业务组件时：调用 `analyze-business-components`。
- 已有结构化页面模型，需要生成候选定位并按优先级排序时：调用 `generate-locator-candidates`。
- 已有候选定位，需要在真实页面里检查唯一性、可见性、可操作性和跨状态稳定性时：调用 `validate-locator-stability`。
- 已有通过校验的定位，需要输出 locator YAML、Page Object 或 Playwright 自动化脚手架时：调用 `generate-automation-assets`。
- 网页元素快速抓取、UI 自动化定位 YAML、表格列/弹窗元素定位，且用户偏向一次性直接产出可用元素清单时：调用 `capture-web-elements`。
- SQL 批量整理、SQL HTML 管理、SQL 去重归类：调用 `sql-html-organizer`。
- 数据库到数据库同步结果核验：调用 `verify-db-sync-result`。
- 第三方接口数据先落中间表/映射表/快照表，再二次写入目标业务表，且已完成核验结果整理、当前只需按统一规范生成中文报告时：调用 `generate-staged-api-migration-report`。
- API 迁移结果、对象存储、文件、ID 映射核验：调用 `verify-api-migration-result`；该 Skill 负责核验逻辑和结构化结果产出，不负责最终主报告排版。
- 读取项目配置 `reporting.default_generate_report`；若该值为 `true`，则核验任务默认继续输出报告，除非用户明确要求“不生成报告”。
- 若用户同时要求“执行 API 迁移核验 + 输出最终统一中文 HTML 报告”，或配置 `reporting.default_generate_report=true`，且链路属于“源/第三方接口 -> 中间层 -> 目标层”，则先调用 `verify-api-migration-result` 产出结构化核验结果，再调用 `generate-staged-api-migration-report` 生成主报告。
- JSON/source_json 解析入库、订单主详表校验：调用 `verify-json-order-ingestion`。
- 基于表结构生成测试数据：调用 `auto-generate-test-data-by-table-schema`。
- 基于实时数据库元数据和业务规则快速构造可执行 INSERT SQL：调用 `quick-build-test-data`。

## 任务执行清单

- 读取项目根目录 `AGENTS.md`，确认测试任务默认使用 `$senior-test-engineer-agent`。
- 读取项目根目录 `AGENT_RULES.md`。
- 读取项目配置：环境变量、`config/test-agent.config.local.json`、`config/test-agent.config.example.json`。
- 完成需求有效性审查，明确不清晰、不合法或高风险点。
- 拆分可立即执行部分和需确认后执行部分。
- 识别任务类型和适用专项 Skill。
- 明确输入材料、测试范围、输出产物路径。
- 执行测试设计、脚本编写、SQL 校验或报告生成。
- 主动识别优化点，并给出原因、收益、落地方式和优先级。
- 执行自检：格式、路径、脱敏、覆盖范围、可执行性。
- 输出结论、产物路径、验证结果、风险和优化建议。

## 敏感信息保护规则

- 禁止在 `AGENT_RULES.md`、测试报告、最终回复中明文输出真实 token、cookie、密码、生产库连接串。
- 敏感配置仅允许放在环境变量或 `config/test-agent.config.local.json`。
- 输出日志、SQL、报告时必须对账号、手机号、token、cookie、密钥、连接串做脱敏处理。
- 若用户直接提供敏感信息，后续引用时必须使用占位符或脱敏值。
- 涉及数据修改 SQL 时，必须先说明风险、备份 SQL、执行 SQL、回滚 SQL、验证 SQL。

## 报告索引规则

- 每次生成测试报告后，必须更新 `reports/index.md`。
- 报告索引至少包含：日期、任务/版本、测试类型、主报告路径、明细路径、结论、阻塞项、负责人。
- 主报告放在 `reports`，明细放在 `reports/details`。
- 主报告只展示摘要、统计、结论和风险，避免堆砌明细。

## 已验证隐性业务逻辑

- 暂无。

## 易错边界条件

- 暂无。

## 特殊测试环境配置

- 暂无。

## 接口/数据库联动规则

- 暂无。

## 历史缺陷高发点

- 暂无。

## 自动化执行前置条件

- 暂无。

## 知识沉淀记录

| 日期 | 来源 | 已验证结论 | 适用范围 | 记录人 |
|---|---|---|---|---|
| <YYYY-MM-DD> | <PRD/原型/接口/数据库/测试执行> | <RULE> | <SCOPE> | 资深测试工程师 Agent |
