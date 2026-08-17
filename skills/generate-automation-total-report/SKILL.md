---
name: generate-automation-total-report
description: Generate a single-page Chinese automation total execution report from UI, API, and UI+API automation artifacts. Use when Codex needs to aggregate existing automation suite JSON, screenshots, request/response evidence, and case metadata into one reviewable HTML report with sequential inline case details, type-specific evidence display, screenshot modal previews, no child-report navigation, and self-check JSON.
---

# 自动化执行总报告

## 目标

生成“以测试用例为核心”的中文自动化执行总报告。报告必须是单页 HTML：从第一个自动化用例到最后一个自动化用例顺序展示，点击用例后在当前页展开明细，不要求读者跳转到 UI、接口或联动子报告。

## 输出规范

必须输出：

- `index.html`：单页自动化总报告。
- `summary.json`：总统计。
- `report-data.json`：总报告结构化数据。
- `report-self-check.json`：报告生成质量自检结果，只作为生成器核验产物，不在 HTML 正文里展示为“报告质量自审”章节。
- `README.md`：报告产物说明。

HTML 必须包含：

- 顶部结论、执行范围、生成时间和统计卡片。
- 一个核心章节：`用例执行明细`。
- 每个用例以可展开卡片展示，保留用例 ID、标题、类型、状态、关联业务用例和接口矩阵 ID。
- UI 用例展示：测试依据、执行步骤、通过标准、断言明细、截图证据。
- API 用例展示：接口、分类、断言明细、请求与响应证据。
- UI+API 用例展示：联动范围、UI 截图、接口请求与响应、跨端一致性断言。
- 截图必须以缩略图显示，点击后在当前页面弹窗预览。
- API 用例不得强行展示“测试依据/执行步骤/通过标准”三栏占位；没有这些字段时，以“接口信息 + 断言明细 + 接口证据”为主。

禁止输出：

- 以“套件结果”“未闭环项”“查看子报告”“打开子报告”为核心的总报告结构。
- 把生成器门禁或自检项作为 HTML 正文主章节。
- 中文 `\uXXXX` 转义。
- 原始 token、cookie、密码、Authorization、X-Auth-Token、secret 等高敏凭据。测试环境地址、普通参数和业务响应可保留，便于排查。
- “失败用例默认展开、通过用例默认收起”这类固定展开规则；用例是否展开由阅读者点击控制。

## 工作流

1. 读取项目规则和自动化执行产物，确认需要聚合的版本号、套件目录和输出目录。
2. 优先读取各套件的 `test-results.json` 和 `summary.json`，保持套件原始顺序与用例原始顺序。
3. 将用例归一化为总报告模型：
   - `related_cases` 只能表示业务测试用例。
   - `matrix_ids` 只能表示接口测试矩阵或接口契约相关编号。
   - 不要把接口矩阵 ID 错写成业务用例 ID。
4. 使用内置脚本生成报告。
5. 检查 `report-self-check.json`，确认统计一致、标题完整、断言三元组完整、截图可访问、截图弹窗可用、正文不跳子报告、没有 Unicode 转义和高敏凭据泄漏。
6. 如修改了报告样式，打开 HTML 做视觉检查，重点看用例卡片可读性、截图缩略图尺寸、弹窗预览、长接口证据滚动和移动端不重叠。

## 脚本用法

默认按当前项目约定聚合：

```bash
python C:/Users/Administrator/.codex/skills/generate-automation-total-report/scripts/render_automation_total_report.py --project-root D:/agent-projects/test --version v1.1
```

默认读取这些目录：

- `automation/reports/<version>/ui-functional/latest`
- `automation/reports/<version>/ui-functional-batch2/latest`
- `automation/reports/<version>/api/latest`
- `automation/reports/<version>/ui-api-integration/latest`

自定义套件时使用 `--suite`，格式为：

```text
suite_id|套件名称|类型|相对或绝对目录
```

示例：

```bash
python scripts/render_automation_total_report.py --project-root D:/agent-projects/test --version v1.1 --suite "ui|UI 自动化|UI|automation/reports/v1.1/ui/latest" --suite "api|接口自动化|API|automation/reports/v1.1/api/latest"
```

类型建议使用 `UI`、`API`、`UI+API`。脚本会把输出写到：

```text
automation/reports/<version>/automation-total/latest
```
