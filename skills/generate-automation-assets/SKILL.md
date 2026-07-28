---
name: generate-automation-assets
description: 把已通过校验的定位结果沉淀为可复用自动化资产，例如 locator YAML、Page Object、字段映射、等待策略和测试脚手架。适用于 UI 自动化初始化、页面对象维护、批量生成 Playwright 辅助层，或把定位资产交付给测试脚本直接消费的场景。
---

# 生成自动化资产

使用本 Skill 时，只消费已经通过校验的定位，不重新猜测定位。

## 共享 references

开始前先读取：

- [共享规则](../ui-locator-orchestrator/references/ui-locator-guidelines.md)
- [页面模型 schema](../ui-locator-orchestrator/references/page-model.schema.json)
- [校验结果 schema](../ui-locator-orchestrator/references/locator-validation.schema.json)
- [运行态材料包 schema](../ui-locator-orchestrator/references/runtime-capture.schema.json)

若输入仍停留在候选集层，或缺少校验结果，禁止直接生成最终自动化资产；应先回退到 `validate-locator-stability`。

## 输入前提

1. 必须同时有 `runtime_manifest.json`、`page_model.json`、`locator_validation.json`。
2. `locator_validation.json` 中至少要存在可消费的 `PASS` 或 `WARN` 项；全量 `FAIL/BLOCKED` 时禁止继续。
3. 知道目标技术栈，默认按 Playwright Python 生成。
4. 明确需要的产物类型；若用户未指定，按“自动化最小可用包”输出。

## 自动化最小可用包

默认优先生成以下 4 类产物：

1. `final_locators.json` 或 `final_locators.yaml`
2. `Page Object`
3. `state helpers`
4. `smoke case`

说明：

- `final_locators.*` 是脚本可直接消费的最终定位基线，不是候选集。
- `Page Object` 负责封装页面区域、动作、行作用域和等待。
- `state helpers` 负责进入默认态、搜索后、弹窗打开后等状态。
- `smoke case` 至少要验证关键路径和关键定位可工作。

## 产物优先级

默认优先生成：

1. `final_locators.*`
2. `Page Object`
3. `state helpers`
4. `smoke case`
5. `locator YAML`

不要把“评审文档”当作主要交付物。若用户没有明确要求，不要优先生成仅供人工阅读的 Markdown 说明。

## 生成规则

- 只使用 `PASS` 的定位作为默认主策略。
- `WARN` 定位只能作为备选，必须显式保留风险说明，不要默默提升为默认主策略。
- `FAIL/BLOCKED` 定位禁止进入最终自动化资产。
- 若某业务区域只有 `WARN/FAIL` 没有 `PASS`，要在产物里明确标注该区域不可直接自动化，必要时要求前端补测试锚点。
- Page Object 名称、字段名、方法名优先沿用结构化页面模型里的业务命名。
- 每个可交互方法都要带等待策略、作用域说明和必要的异常处理。
- 表格、树、弹窗、分页、级联、下拉不能只输出裸定位，必须输出方法封装。
- 表格行内操作必须使用行作用域封装，例如 `row.getByRole(...)`，不能把全局按钮定位直接写进页面对象。
- 生成 YAML 或 JSON 时保持页面、区域、字段、动作四层结构，便于后续 diff 和维护。
- 若已探明登录态策略，例如 cookie、header、localStorage，必须把“如何进入页面”一并写入辅助层或产物说明。

## 状态要求

默认至少支持以下状态：

1. `default`
2. `searched`
3. `<action>_modal_opened` 或 `<action>_drawer_opened`

若当前任务只覆盖了默认态，必须在交付中明确说明“状态覆盖不完整”，不要伪装成完整可用的自动化资产。

## 复杂控件规则

- 下拉：输出打开、选择、清空等方法，不要只给一个输入框定位。
- 级联：输出展开、搜索、选择路径等方法，不要只给只读 input 定位。
- 弹窗：先定位容器，再输出容器内字段和动作方法。
- 团队树、左侧面板、卡片集合：先输出集合或区域作用域，再输出子元素方法。
- 表格列定位可以保留在最终定位资产中，但表格单元格操作应优先方法化。

## 推荐文件命名

- `<page_key>.final-locators.json`
- `<page_key>.final-locators.yaml`
- `<PageName>Page.py`
- `<page_key>_state_helpers.py`
- `<page_key>_smoke.spec.py`

## 最小输出内容

- 资产路径。
- 输入来源：`runtime_manifest.json`、`page_model.json`、`locator_validation.json`。
- 产物之间的依赖关系。
- 哪些定位是主策略，哪些是备选。
- 哪些区域仍需人工复核或补测试锚点。
- 是否已包含登录态进入策略和状态切换能力。

## 完成后的回复

至少汇报：

1. 生成了哪些资产。
2. 每个资产消费了哪些已验证定位和哪些输入文件。
3. 是否存在只带 `WARN` 备选的元素或区域。
4. 是否已具备最小自动化可运行条件：登录态、Page Object、状态 helper、smoke case。
5. 是否可以直接接入测试环境，还是仍需补锚点或人工修正。
