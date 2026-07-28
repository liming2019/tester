---
name: analyze-business-components
description: 将页面运行态材料整理成可维护的业务页面模型，识别筛选区、工具栏、表格、分页、弹窗、树、页签和行内操作等组件边界。适用于已有 DOM、截图、无障碍语义或运行态快照，要求抽取业务组件、页面分区、字段字典或为后续定位生成提供结构化输入的场景。
---

# 识别业务组件

使用本 Skill 时，负责把页面材料从“浏览器结构”翻译成“测试和业务可消费的页面模型”。

## 共享 references

开始前先读取：

- [共享规则](../ui-locator-orchestrator/references/ui-locator-guidelines.md)
- [运行态材料包 schema](../ui-locator-orchestrator/references/runtime-capture.schema.json)
- [页面模型 schema](../ui-locator-orchestrator/references/page-model.schema.json)

输入运行态材料包时，以 `runtime-capture.schema.json` 为上游硬约定。输出页面模型时，以 `page-model.schema.json` 为当前阶段硬约定，以共享规则里的命名约定为软规则。

## 输入前提

- 优先消费 `capture-web-runtime` 的输出。
- 若只有 DOM 或截图，也可以工作，但要显式说明缺少运行态信息带来的歧义。
- 输入里至少要有页面标题、主要截图或 DOM、目标页面说明。

## 工作流

1. 先识别页面级边界：页面名称、入口路径、主内容区域、是否有侧栏或页签。
2. 再识别业务区域：筛选区、工具栏、结果表格、分页、统计卡片、树、弹窗、抽屉、右键菜单。
3. 在每个区域内拆字段和动作：输入框、下拉、日期、复选框、主按钮、次按钮、行内操作、自定义文本/图标触发器。
4. 标记集合元素与单元素的区别，例如表格行、树节点、卡片列表、标签集合。
5. 对文本重复、区域归属不清、需要运行态才能确认的元素，放入歧义清单。

## 建模规则

- 优先按用户可感知的业务语义分区，不要被 DOM 层级牵着走。
- 不要给看不见、禁用或未展开的控件强行补业务结论。
- 同名按钮必须带区域或状态作用域，例如 `toolbar.export_button`、`detail_modal.confirm_button`。
- 同 placeholder、同文案或同按钮名但位于不同业务面板的元素，必须按面板/模块作用域拆分，例如 `primary_category_name_input`、`secondary_category_name_input`，禁止合并成一个全局字段。
- 自定义触发器若具备明确业务语义，例如 `div.add`、图标+文字入口、标题栏操作入口，也必须入模，不得因为不是原生 button 就丢弃。
- 表格列、行内操作、树节点操作要按相对作用域建模，不要当成普通全局按钮。
- 若页面材料不足以支持判断，明确标记 `pending_confirmation`，不要脑补业务名称。

## 建议输出结构

```yaml
page:
  key: user_manage
  name: 用户管理
regions:
  filters:
    fields: ...
  toolbar:
    actions: ...
  table:
    columns: ...
    row_actions: ...
  modals: ...
ambiguities:
  - repeated_text: "确定"
    reason: "默认页和弹窗内均存在"
```

## 完成后的回复

至少汇报：

1. 识别出的页面区域。
2. 每个区域下的核心字段和动作数量。
3. 无法确认或需要补材料的歧义项。
4. 是否已经足够进入候选定位生成阶段。
