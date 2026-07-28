---
name: manage-test-agent-plugin-skills
description: 维护资深测试工程师 Agent 插件内置 Skills。用于以 senior-test-engineer-agent 插件内 Skill 为唯一源，检查并归档全局同名测试 Skill、对比插件内外差异、必要时先合入全局较新内容、排除系统 Skill、更新入口 Agent 调度规则、执行插件校验、更新 cachebuster、重新安装插件，并输出归档/迁移报告和 Git 提交前检查清单。
---

# Manage Test Agent Plugin Skills

使用本 Skill 时，你负责维护 `senior-test-engineer-agent` 插件本身，而不是执行具体测试业务。

## 适用场景

当用户提出以下需求时使用本 Skill：

1. 将资深测试工程师 Agent 插件内 Skill 作为唯一维护源。
2. 检查并归档全局同名测试 Skill，避免插件和全局双份漂移。
3. 检查插件 Skill 与全局 Skill 差异。
4. 处理插件内外同名 Skill 冲突。
5. 准备把插件提交到 Git 或做分支合并。
6. 更新插件版本、校验插件、重新安装插件。

## 默认路径

1. 插件源目录：`C:\Users\Administrator\plugins\senior-test-engineer-agent`
2. 插件 Skill 目录：`C:\Users\Administrator\plugins\senior-test-engineer-agent\skills`
3. 全局 Skill 目录：`C:\Users\Administrator\.codex\skills`
4. 默认个人 marketplace：`C:\Users\Administrator\.agents\plugins\marketplace.json`
5. 若当前维护工作发生在 Git worktree 或功能分支目录，以该真实源目录为准；不要把 `.codex/plugins/cache` 识别为插件源目录。

## 插件唯一源原则

1. 测试 Agent 依赖的专项 Skill 以插件内目录为唯一源：`C:\Users\Administrator\plugins\senior-test-engineer-agent\skills`。
2. 全局目录 `C:\Users\Administrator\.codex\skills` 不再保存同名测试专项 Skill；若发现同名 Skill，必须先对比差异，再归档或删除全局副本。
3. 若全局副本比插件内副本更新，必须先把有效差异合入插件，再归档全局副本。
4. 若差异只是编码修正、缓存文件、IDE 文件、运行产物或本地配置，不得用全局副本覆盖插件内版本。
5. 系统 Skill 仍保留在全局或系统目录，不迁入本插件。
6. `.codex/plugins/cache`、`.codex/plugins/cache-backup` 只作为安装或运行缓存，不得作为 Skill 规则变更的唯一落点；如需验证缓存效果，必须先改真实源目录或分支，再同步缓存或重新安装。

## 插件内置测试专项 Skill

默认维护以下测试 Agent 依赖的专项 Skill：

1. `test-object-analysis`
2. `lanhu-to-testcase`
3. `lanhu-requirements-extractor`
4. `extract-functional-test-points`
5. `generate-ui-automation-testcases`
6. `generate-playwright-from-ui-testcases`
7. `ui-locator-orchestrator`
8. `capture-web-runtime`
9. `analyze-business-components`
10. `generate-locator-candidates`
11. `validate-locator-stability`
12. `generate-automation-assets`
13. `capture-web-elements`
14. `api-test-design`
15. `linker-gateway-api-test`
16. `auto-generate-test-data-by-table-schema`
17. `quick-build-test-data`
18. `verify-db-sync-result`
19. `generate-staged-api-migration-report`
20. `verify-api-migration-result`
21. `verify-json-order-ingestion`
22. `sql-html-organizer`

## 禁止迁移的系统 Skill

以下 Skill 属于系统或通用开发工具链，不得复制进本插件：

1. `plugin-creator`
2. `skill-creator`
3. `skill-installer`
4. `openai-docs`
5. `imagegen`

若用户要求迁移系统 Skill，必须说明不建议迁移的原因：会造成官方更新丢失、维护分叉、插件膨胀和职责边界混乱。

## 归档/同步流程

1. 先定位真实插件源目录：优先当前 Git 仓库或 worktree；若同时存在缓存目录和源目录，以真实源目录为唯一修改目标。
2. 读取插件源目录和全局 Skill 目录。
3. 对允许维护的测试专项 Skill 逐个检查：插件内是否存在、全局是否存在、归档目录是否存在。
4. 若插件内缺失而全局存在，先向用户确认是否恢复到插件；不得静默迁移。
5. 若插件内和全局均存在，先比较文件清单、哈希、最新修改时间和关键内容差异。
6. 若全局内容更新且属于有效规则/脚本变化，先合入插件内副本。
7. 若差异属于编码修正、缓存文件、IDE 文件、运行产物或本地配置，保留插件内版本并记录原因。
8. 对比完成后，将全局同名测试 Skill 移动到 `C:\Users\Administrator\.codex\skills-archive\test-agent-skills-<yyyyMMdd>`。
9. 不移动或删除系统 Skill；不移动 `.system`。
10. 归档后再次确认全局同名测试 Skill 不存在。
11. 检查入口 Agent 的专项 Skill 调度规则，确保优先使用插件内 Skill。
12. 检查所有 `agents/openai.yaml` 是否为 UTF-8 编码；若不是，转换插件内副本为 UTF-8。
13. 对所有新增或更新 Skill 执行基础校验。
14. 校验整个插件。
15. 更新插件 cachebuster 版本。
16. 重新安装插件；若为了即时验证同步缓存，必须说明缓存是派生结果而非唯一修改落点。
17. 输出归档/迁移报告和 Git 提交前检查清单。

## 敏感信息保护

归档或合入前必须扫描明显敏感文件名：

1. `.env`
2. `*.local.*`
3. `config.local.*`
4. `credentials*`
5. `secret*`
6. `token*`
7. `cookie*`
8. `password*`

若发现疑似敏感文件，必须暂停处理该文件并说明路径。不得把真实 token、cookie、密码、生产库连接串写入插件仓库、归档/迁移报告或最终回复。

## 校验要求

归档或同步完成后必须至少执行：

1. 全局同名测试 Skill 已不存在或已归档。
2. 每个插件内置测试 Skill 的 `SKILL.md` 存在性检查。
3. `agents/openai.yaml` UTF-8 编码检查。
4. `skill-creator/scripts/quick_validate.py` 校验新增/更新 Skill。
5. `plugin-creator/scripts/validate_plugin.py` 校验插件。
6. `plugin-creator/scripts/update_plugin_cachebuster.py` 更新版本。
7. `codex plugin add senior-test-engineer-agent@personal` 重新安装。
8. `codex plugin list` 确认插件 installed, enabled。

## 输出报告

最终回复必须包含：

1. 插件源目录。
2. 已归档全局 Skill 清单和归档路径。
3. 合入插件的差异清单。
4. 跳过或保留差异清单及原因。
5. 冲突处理结果。
6. 校验结果。
7. 新插件版本。
8. 重新安装状态。
9. 建议 Git 提交范围。

## Git 提交前检查清单

提交前必须提醒用户检查：

1. 不提交 `.codex/plugins/cache`。
2. 不提交 `test-agent.config.local.json`、`.env`、日志、运行报告、临时文件。
3. 只提交插件源目录中的 `.codex-plugin`、`skills`、`agents`、必要模板和脚本。
4. 功能分支只提交实际规则/模板/Skill 变化。
5. 合并发布分支前再统一更新 cachebuster。
6. 若本次曾修改缓存目录，必须确认同样的有效变更已落到真实源目录或分支，且提交范围只指向源仓内容。
