---
name: ui-locator-orchestrator
description: 编排一条基于 Playwright 的 UI 自动化定位产线，串联真实页面采集、业务组件识别、候选定位生成、稳定性校验和自动化资产输出。适用于用户要求从网页 URL、运行态页面、DOM/截图材料批量生成或维护 UI 自动化定位、Page Object、locator YAML、定位治理方案，或需要拆分 UI 自动化定位相关子任务的场景。
---

# UI 定位流程编排

使用本 Skill 时，负责把 UI 自动化定位任务拆成稳定的多阶段流程，而不是直接凭 DOM、截图或单次录制结果输出最终脚本。

## 共享 references

开始编排前先读取：

- [ui-locator-guidelines.md](references/ui-locator-guidelines.md)

需要校对阶段产物结构时，再按阶段读取：

- [runtime-capture.schema.json](references/runtime-capture.schema.json)
- [page-model.schema.json](references/page-model.schema.json)
- [locator-candidate.schema.json](references/locator-candidate.schema.json)
- [locator-validation.schema.json](references/locator-validation.schema.json)

## 工作流

1. 先确认输入是否够用：页面 URL、认证方式、目标页面、是否指定模块、要覆盖的状态、目标产物。
2. 若缺少真实运行态材料，先调用 `capture-web-runtime`。若用户只要求一次性抓取业务元素 YAML，可改用 `capture-web-elements`。
3. 若未指定模块，先识别全页面的安全动态入口集合；对每个可安全展开的入口生成状态矩阵，例如弹窗、抽屉、级联面板、下拉面板、行内菜单。
4. 调用 `analyze-business-components` 把默认态和已展开状态的材料整理为结构化页面模型。
5. 调用 `generate-locator-candidates` 为每个业务元素生成候选定位集合。
6. 调用 `validate-locator-stability` 在真实页面里做唯一性、可见性、可操作性和跨状态稳定性校验。
7. 只有在 `runtime_manifest.json`、`page_model.json` 和 `locator_validation.json` 都齐全，且至少存在可消费的 `PASS/WARN` 结果时，才能交给 `generate-automation-assets` 生成最终自动化资产。
8. 最终汇总覆盖范围、失败项、剩余风险和对前端测试锚点的建议。

## 何时直接改调子 Skill

- 只缺真实运行态采集：直接用 `capture-web-runtime`。
- 只有 DOM、截图、a11y 材料，需要先做页面分区：直接用 `analyze-business-components`。
- 业务组件已经清楚，只差候选定位：直接用 `generate-locator-candidates`。
- 已有候选定位，需要验收或排查漂移：直接用 `validate-locator-stability`。
- 已有通过校验的定位，需要沉淀成代码或 YAML：直接用 `generate-automation-assets`。

## 编排规则

- 优先使用真实页面运行态，不要把静态 DOM 当成唯一事实源。
- 不要跳过校验直接输出最终定位。
- 不要只生成“评审文档”就结束；若目标是 UI 自动化，最后应落到 `final_locators.*`、`Page Object`、`state helpers` 或 `smoke case`。
- 若用户未指定模块，默认抓取全页面范围内“可见、可操作的元素”和“业务动态操作元素”。
- 业务动态操作元素至少包括：会打开弹窗、抽屉、下拉、级联、右键菜单、行内操作菜单或状态面板的触发元素，以及自定义文本/图标触发器，例如 `div.add`、图标加文字的自定义入口、可点击的业务标题栏操作。
- 未指定模块时，不要只停在动态入口本身；必须继续展开所有安全动态入口并抓取展开后的内部元素。
- “安全动态入口”默认指不会直接提交写操作的入口，例如打开弹窗、展开抽屉、打开下拉、展开级联、展开行内菜单；不包括保存、确认删除、提交落库等高风险动作。
- 若用户明确指定模块、区域或控件范围，只更新该模块相关材料，不重跑全页面其他区域。
- 同一页面至少区分默认态、查询后或加载后、弹窗打开后。涉及表格、树、分页、权限差异时，再补充状态。
- 若前端已提供 `data-testid` 或等价测试锚点，必须保留并把它当作最高优先级。
- 若某元素始终无法生成稳定定位，标记为 `needs-testability-contract`，不要强行塞入脆弱 XPath。
- 交付中要区分“可立即用于自动化”的定位与“仅供人工复核”的候选。
- 当任务是“更新已有页面资产”时，若指定了模块，默认执行模块级增量更新；若未指定模块，默认刷新整页资产。
- 对重复文案、重复 placeholder 或重复按钮，默认先按业务区域建模，再生成定位；禁止在未建区域作用域时把重复元素压成单个全局元素。

## 阶段输入输出约定

- `capture-web-runtime`：输出满足 `runtime-capture.schema.json` 的运行态材料包，至少包含页面标题、最终 URL、状态矩阵、截图、快照和异常说明。
- `analyze-business-components`：输出结构化页面模型，至少包含区域、字段、动作、集合元素和歧义项。
- `generate-locator-candidates`：输出候选定位集合，包含主备策略、作用域、风险标签、适用状态。
- `validate-locator-stability`：输出 PASS/WARN/FAIL 校验结果、证据和失败原因。
- `generate-automation-assets`：输出最终自动化资产和消费说明，不再重新猜测定位；默认目标是 `final_locators.*`、`Page Object`、`state helpers`、`smoke case`。

## 最终回复

至少汇报：

1. 使用了哪些阶段以及为什么这样编排。
2. 每个阶段的主要产物路径或结构。
3. 通过校验的定位数量与失败数量。
4. 剩余高风险点和是否阻塞自动化落地。
5. 是否建议前端补测试锚点。
