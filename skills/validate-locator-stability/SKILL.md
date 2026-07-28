---
name: validate-locator-stability
description: 在真实页面中回放和验证候选定位，检查唯一命中、可见性、可操作性、跨状态稳定性以及对动态结构的脆弱性。适用于 UI 自动化定位上线前验收、定位失效排查、批量回归已有 locator，或需要筛出不稳定 XPath 和 CSS 的场景。
---

# 校验定位稳定性

使用本 Skill 时，负责做浏览器中的事实校验。没有经过这一步的候选定位，不要视为最终可用定位。

## 共享 references

开始前先读取：

- [共享规则](../ui-locator-orchestrator/references/ui-locator-guidelines.md)
- [候选定位 schema](../ui-locator-orchestrator/references/locator-candidate.schema.json)
- [校验结果 schema](../ui-locator-orchestrator/references/locator-validation.schema.json)

## 输入要求

1. 候选定位集合，优先来自 `generate-locator-candidates`。
2. 可进入真实页面的 URL、认证方式和必要账号。
3. 需要覆盖的状态矩阵，例如默认态、弹窗态、搜索后、翻页后。
4. 输出目录和证据归档方式。

## 校验清单

对每个候选定位至少检查：

1. 是否唯一命中。
2. 是否可见。
3. 是否可点击、可输入或可选择。
4. 切换到其他目标状态后是否仍然稳定。
5. 是否依赖动态 id、通用 class、绝对 XPath 或层级过深的 CSS。
6. 是否受语言、权限、分页、虚拟滚动或异步渲染影响。

## 判定规则

- `PASS`：唯一、可见、可操作，且在声明适用的状态下稳定。
- `WARN`：当前可用，但存在明显漂移风险，例如文本重复、国际化、异步抖动、隐藏重复节点。
- `FAIL`：非唯一、不可见、不可操作，或跨状态直接失效。
- 如果多个候选都通过，优先级按 `test_id > role > label > placeholder > text > relative css/xpath` 选择。

## 执行规则

- 校验必须回到真实浏览器执行，不要只凭静态 DOM 下结论。
- 表格行操作必须在明确的行或记录作用域中验证。
- 弹窗、抽屉和右键菜单内元素必须在容器打开后验证。
- 若页面存在懒加载或虚拟滚动，要明确记录滚动条件和定位可见范围。
- 若某个元素只有 `WARN` 级候选，不要自动升格为最终资产。

## 建议输出结构

```yaml
search_button:
  chosen: role
  result: PASS
  states_checked: [default, searched]
  evidence:
    - screenshots/default.png
  notes: []
```

## 完成后的回复

至少汇报：

1. PASS、WARN、FAIL 的数量。
2. 阻塞自动化落地的失败项。
3. 高风险但暂时可用的定位项。
4. 是否建议回退到 `generate-locator-candidates` 重生候选，还是直接要求前端补测试锚点。
