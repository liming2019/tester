# 文件管理与 Git 纳管规则

## 目录边界

| 路径 | 用途 | Git 纳管 |
| --- | --- | --- |
| `inputs/` | 需求、接口文档、原型、截图等输入材料 | 是 |
| `testpoints/` | 测试点 XMind 或 Markdown 降级文件 | 是 |
| `testcases/` | 测试用例、接口矩阵和用例基线 | 是 |
| `automation/` | 可复用执行器、公共报告模板、接口元数据和 suite | 是 |
| `sql/readonly/` | 长期可复用只读核验 SQL | 是 |
| `sql/testdata/final/` | 已确认长期复用的测试数据构造 SQL，必须有备份、执行、回滚和验证说明 | 是 |
| `reports/current.md` | 当前版本级有效结论入口 | 是 |
| `reports/final/` | 已确认长期纳管的最终报告包 | 是 |
| `outputs/index.md`、`outputs/final/` | 最终交付物索引和确认交付物 | 是 |
| `docs/rules/` | 通用执行规则和治理规则 | 是 |
| `docs/knowledge/` | 当前项目已验证业务知识 | 是 |
| `work/` | 本地过程产物、运行批次、临时脚本、敏感证据 | 否 |
| `config/*agent.config.local.json`、`config/test.json` | 本地真实环境配置 | 否 |

## 需求输入基线

- 从原型、蓝湖、HTML 页面、截图或其他外部材料提取需求时，提取结果先进入 `work/versions/<VERSION-ID>/runs/<RUN-ID>/`，默认视为过程稿，不作为测试点、测试用例、研发交付或自动化资产的正式输入。
- 用户确认需求提取通过后，若下一步要基于该需求生成测试点、测试用例、测试矩阵、研发交付材料或执行其他测试任务，必须先询问用户是否冻结 PRD、是否确认为需求基线。
- 用户确认冻结后，必须将已确认 PRD 复制到 `inputs/requirements/<VERSION-ID>/`，并以该目录下的需求文件作为后续测试资产唯一正式输入；不得继续引用 `work/` 下的过程稿作为正式输入。
- `inputs/requirements/<VERSION-ID>/` 建议至少包含已确认 PRD 和 `README.md`；`README.md` 记录来源、确认时间、确认人或确认来源、当前状态、后续引用文件和剩余待确认项。
- `work/versions/<VERSION-ID>/index.md` 仅作为过程追溯入口，不作为需求基线入口。需求基线确认并沉淀到 `inputs/` 后，若用户确认不再需要过程证据，可以清理对应 `work/versions/<VERSION-ID>/`。
- 清理 `work/` 前必须确认已沉淀到 `inputs/` 的需求基线、后续测试资产引用路径和必要证据索引均已可追溯；不得删除尚未沉淀的唯一需求来源。

## 直接需求输入

- 用户直接提供需求并要求生成测试点、测试用例、测试矩阵、研发交付材料或执行其他测试任务时，必须先确认该需求是否有版本号或研发分支号。
- 若用户提供版本号，输入文件放入 `inputs/requirements/<VERSION-ID>/`；若用户提供研发分支号，输入文件放入 `inputs/requirements/<BRANCH-ID>/`。
- 若用户未提供版本号或分支号，必须先向用户确认标识；若用户明确不提供，则使用 `inputs/requirements/VERSION-adhoc-<简短名称>/`，并在 README 和后续产物中标记为临时需求输入。
- 直接需求输入落盘后，再开始测试点、测试用例、测试矩阵、研发交付材料或其他测试任务；不得只基于会话文本生成长期测试资产。
- 直接需求输入文件必须保留原始需求内容、用户补充确认口径、版本或分支标识、创建时间和后续引用说明。

## 版本工作区

- 每个版本或并行测试批次必须先分配版本工作区。
- 版本号类工作区固定使用 `work/versions/VERSION-<主版本>-<次版本>-<修订版本>/`，例如 `V1.1.1` 使用 `work/versions/VERSION-1-1-1/`。
- 临时批次使用 `work/versions/VERSION-adhoc-<简短名称>/`。
- 禁止默认拼接日期、序号或 suite 名称造成同一版本多目录。
- 每个版本工作区必须维护 `index.md`，记录本版本下每次运行批次的输入、输出、结论、是否可复用、是否含敏感依赖和更新时间。

## 单次运行批次

- 每次执行测试、复测、数据核验、报告重建或缺陷诊断时，必须在所属版本工作区下分配唯一运行批次号。
- 格式为 `RUN-yyyyMMdd-HHmmss_<模块或小点>_<执行类型>`。
- 同一用户任务或同一触发命令覆盖多个接口/多个测试项时，只能分配一个共享 `RUN-*` 目录。
- 批次总入口固定为 `reports/index.md` 和 `reports/index.html`。
- 接口主报告放 `reports/interfaces/`，执行明细放 `reports/details/`，JSON 证据放 `evidence/`。

## 当前结论入口

- `reports/current.md` 只记录版本级当前有效结论、风险、阻塞、下一步动作和正式报告入口。
- 维护粒度固定为一个版本一条记录。
- 不得展开接口、模块、小点、作废范围或执行批次明细。
- 当报告影响某个版本的最新有效结论、推荐入口或版本风险时，必须同步更新 `reports/current.md`。

## 正式报告

- 报告先在 `work/versions/<VERSION-ID>/runs/<RUN-ID>/` 生成和自审。
- 只有确认需要长期纳管的正式报告，才复制或生成到 `reports/final/`。
- 正式报告包目录名必须使用 ASCII slug，格式建议为 `<version>_<suite-or-module>_<scope>_final_report`，例如 `V1.1.1_matrix_full_final_report`；中文标题写入包内 `README.md` 和 `manifest.yaml`。
- 正式报告包采用“Git 轻量可评审包 + 完整证据归档”的策略。
- 单个正式报告包 Git 纳管软上限为 10 MB，硬上限为 20 MB；单文件软上限为 2 MB，硬上限为 5 MB；`evidence/` 下 JSON 合计软上限为 3 MB，硬上限为 8 MB。
- 删除或剥离正式包内 HTML/JSON 文件前，必须同步更新主报告链接、接口报告链接、`manifest.yaml` 和报告包门禁脚本。

## Git 纳管

- Git 只纳管稳定资产和轻量入口：规则、矩阵、可复用自动化、只读 SQL、示例配置、当前结论和最终确认报告。
- Git 默认不纳管历史报告流水、普通明细 HTML、普通 JSON 证据、完整原始响应、`work` 过程产物、截图、压缩包、运行缓存和本地真实配置。
- 正式报告包中的逐项完整 JSON 默认视为归档证据，不作为 Git 必纳管内容；Git 内应优先保留汇总 JSON、`evidence-index.md/json` 或 `manifest.yaml` 中的证据索引。
- 提交前必须检查 `git status --short --branch` 和暂存范围。
