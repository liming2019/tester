---
name: generate-ui-automation-report
description: 基于 UI 自动化执行结果、测试用例元数据、断言明细、截图证据、Playwright/JUnit/JSON 产物生成可评审的中文 HTML 测试报告，并执行报告质量自审。Use when Codex needs to turn UI automation results into a reviewable report, rebuild an existing UI automation report, check report evidence quality, enforce case/assertion/screenshot traceability, or avoid free-form report templates.
---

# 生成 UI 自动化报告

使用本 Skill 时，目标不是复用某一个固定页面样式，而是固定 UI 自动化报告的数据契约、信息架构和外部质量门禁。视觉样式可以按项目调整，但字段、证据链和交付前自审不能省略。

## 输入前提

至少确认以下输入：

1. UI 自动化执行结果 JSON，例如 `test-results.json`。
2. 报告摘要 JSON，例如 `summary.json`；若项目没有摘要文件，先从执行结果中派生同等字段。
3. 截图证据目录；截图路径必须能从项目根目录或报告输出目录解析。
4. 目标输出路径，默认写入项目 `automation/reports/<版本>/<类型>/latest/index.html`。

若输入用例缺少 `用例ID`、`测试标题`、`断言明细` 或 `截图证据`，不得直接标记正式报告通过；必须在外部自审结果中明确失败或风险。

## 报告原则

需要确认报告信息架构、证据链或可读性标准时，读取：

- [ui-automation-report-principles.md](references/ui-automation-report-principles.md)

不要把参考文件全文复制进报告；只按其中原则组织产物。

## 固定契约

报告输入和输出门禁以以下文件为准：

- [report_contract.json](assets/report_contract.json)

必须保持以下核心字段可追溯：

1. 用例：`id`、`title`、`status`、`related_cases`、`basis`、`steps`、`pass_criteria`。
2. 断言：`check`、`expected`、`actual`、`passed`。
3. 证据：截图名称、截图路径、截图存在性。
4. 缺陷：缺陷编号、标题、关联用例、失败断言、证据。

## 生成流程

1. 读取项目 `AGENT_RULES.md` 和当前报告输入文件。
2. 运行渲染脚本生成 HTML 和可选结构化归一化 JSON。
3. 运行校验脚本检查字段、统计、断言、截图、失败优先展示、敏感信息和编码。
4. 若校验失败，先修正输入、脚本或报告，不要把报告作为最终交付。
5. 若用户正在浏览报告或反馈 UI 问题，必须打开最终 HTML 或截图复核实际渲染效果。

推荐命令：

```bash
python <skill_dir>/scripts/render_ui_automation_report.py --summary <summary.json> --results <test-results.json> --output <index.html> --project-root <project_root> --write-normalized-json <report-data.json>
python <skill_dir>/scripts/validate_ui_automation_report.py --summary <summary.json> --results <test-results.json> --html <index.html> --project-root <project_root> --output-json <self-check.json>
```

如需替换视觉皮肤，可给渲染脚本传入 `--css-file <custom.css>`。自定义 CSS 只能改变视觉表现，不能删除固定业务章节或字段。

## 输出要求

最终报告必须包含：

1. 报告结论：版本、范围、环境脱敏说明、执行时间、是否可通过。
2. 执行统计：总数、通过、失败、阻塞、通过率、断言数、截图数。
3. 失败影响：失败用例、失败断言、关联需求/用例、缺陷编号、证据。
4. 用例执行明细：摘要行保持可扫读，展开状态不作为固定规则，可由读者按需打开；不再额外展示重复的概览表。
5. 断言明细：每条断言展示检查项、期望、实际、结果。
6. 截图证据：默认缩略图展示，点击缩略图在报告内弹窗预览，并提供原图链接，不允许把大截图作为主内容铺满。
7. 报告 HTML 不展示生成器质量门禁；门禁结果只写入 `report-self-check.json`，供交付前核验和问题排查使用。

## 外部质量门禁

生成后必须至少校验：

1. 执行统计和用例明细一致。
2. 每条用例都有非空测试标题。
3. 每条断言都有检查项、期望、实际和结果。
4. 失败用例和失败断言一致，不能只写 `passed` 或 `failed`。
5. 截图路径存在且能从 HTML 访问。
6. 截图点击后在报告内弹窗预览，不直接跳离报告。
7. 首页先展示结论、统计、失败影响和风险，再展示用例执行明细；HTML 正文不展示重复的概览表。
8. 报告、JSON 和最终回复不泄露 token、cookie、密码、密钥、连接串。
9. 文件为 UTF-8 无 BOM，中文直接输出，不使用 `\uXXXX` 转义。
10. HTML 正文不展示生成器质量门禁表，不出现 `报告质量自审`、`报告产物校验` 等面向执行器的核验区块。

## 最终回复

至少汇报：

1. 使用的输入文件。
2. 生成的 HTML 报告路径。
3. 校验结果和失败/风险项。
4. 执行统计摘要。
5. 若当前目录不是 Git 仓库或存在未处理的历史改动，明确说明。
