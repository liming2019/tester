---
name: generate-locator-candidates
description: 根据结构化页面模型和运行态材料，为每个业务元素生成按优先级排序的候选定位策略集合，并标注主备策略、适用状态和风险。适用于需要为 Playwright UI 自动化生成 locator 候选、补全 Page Object 字段、或在定位失效修复前先建立可校验候选集的场景。
---

# 生成候选定位

使用本 Skill 时，负责生成“候选集”，不是负责宣布哪个定位已经可以直接进仓库。

## 共享 references

开始前先读取：

- [共享规则](../ui-locator-orchestrator/references/ui-locator-guidelines.md)
- [候选定位 schema](../ui-locator-orchestrator/references/locator-candidate.schema.json)

若输入来自页面模型，还要对齐：

- [页面模型 schema](../ui-locator-orchestrator/references/page-model.schema.json)

## 输入要求

1. 有结构化页面模型，优先来自 `analyze-business-components`。
2. 最好同时有运行态截图、DOM 或 a11y 材料。
3. 知道元素所在作用域和适用状态。

## 生成顺序

Playwright 场景下，固定按以下优先级尝试：

1. `test_id`
2. `role`
3. `label`
4. `placeholder`
5. 唯一文本锚点
6. 唯一相对 CSS 或 XPath

## 生成规则

- 非表格、非集合元素的主定位必须以唯一命中为目标。
- 表格行、树节点、卡片集合允许先生成集合定位，再补相对行内操作。
- 弹窗、抽屉、右键菜单内元素必须先有容器作用域，再生成内部定位。
- 不要把通用 class、动态 id、绝对 XPath、深层级 CSS 当主定位。
- 如果只能生成脆弱定位，保留为候选并打上 `fragile` 风险标签。
- 如果没有足够稳定的候选，输出 `needs-testability-contract`，提示需要前端补测试锚点。

## 建议输出结构

```yaml
search_button:
  scope: toolbar
  primary:
    type: role
    path: page.getByRole("button", { name: "搜索" })
  fallbacks:
    - type: text
      path: 搜索
  applies_in:
    - default
    - searched
  risk_tags: []
```

## 风险标签

至少使用以下标签中的合适项：

- `fragile`
- `text-duplicate-risk`
- `dynamic-attribute`
- `state-dependent`
- `i18n-sensitive`
- `needs-testability-contract`

## 完成后的回复

至少汇报：

1. 生成了多少个元素的候选定位。
2. 每类定位策略的分布。
3. 哪些元素只有高风险候选。
4. 哪些元素应该先交给 `validate-locator-stability`，哪些需要前端补锚点。
