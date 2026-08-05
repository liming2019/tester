# <PROJECT_NAME>

本仓库用于沉淀测试资产、自动化执行器、只读 SQL、正式测试报告和项目级测试治理规则。

## 快速入口

- 项目测试入口规则：[AGENTS.md](AGENTS.md)
- 项目级测试准则：[AGENT_RULES.md](AGENT_RULES.md)
- 规则与业务知识索引：[docs/README.md](docs/README.md)
- 当前有效测试结论：[reports/current.md](reports/current.md)
- 正式报告目录：[reports/final/](reports/final/)
- 测试用例/矩阵：[testcases/](testcases/)
- 自动化资产：[automation/](automation/)
- 只读 SQL：[sql/readonly/](sql/readonly/)

## 当前状态

当前版本结论以 `reports/current.md` 为准。该文件只维护版本级当前有效结论，固定一个版本一条记录；接口级、模块级、批次级明细进入正式报告包或本地版本工作区。

## 执行规则摘要

- 测试相关任务默认按 `$senior-test-engineer-agent` 和 `AGENT_RULES.md` 执行。
- 执行时先读 `AGENT_RULES.md`，再按任务对象、执行动作、产物目标、版本范围、风险域匹配加载 `docs/rules/` 或 `docs/knowledge/` 的必要文档。
- 过程报告先进入 `work/versions/<VERSION-ID>/runs/<RUN-ID>/`，自审通过并确认长期纳管后再进入 `reports/final/`。
- `reports/final/` 下正式报告包目录统一使用 ASCII slug，例如 `V1.1.1_matrix_full_final_report`；中文标题写入包内 `README.md` 和 `manifest.yaml`。
- `reports/final/` 采用“Git 轻量可评审包 + 完整证据归档”策略；完整逐项 JSON 和大体积明细优先归档到来源 `RUN-*` 或外部制品包。

## 常用门禁

正式报告包门禁：

```powershell
python automation/validate_report_package.py --report-dir .\reports\final\<正式报告包目录>
```

仓库文件卫生门禁：

```powershell
python automation/validate_repository_hygiene.py
```
