---
name: "capture-web-elements"
description: "通过用户提供的网页 URL 和 token 打开页面，等待渲染完成后抓取业务元素、表格列、弹窗元素和定位路径，并导出 schema_version=2 的分层 locator YAML。适用于 UI 自动化定位配置生成、页面元素盘点、表格行/列定位建模、点击按钮后弹窗元素捕获等场景。"
---

# 抓取网页元素

使用 Python + Playwright 打开用户提供的页面，注入 token，等待页面稳定后抓取 DOM 元素和定位路径。默认抓取当前范围内具备业务语义的可见控件，包括输入框、下拉、按钮、表格操作、表格列、弹窗触发器、抽屉触发器、下拉/级联触发器，以及自定义文本/图标触发器等业务动态操作元素。

## 工作流

1. 确认认证注入方式。优先 `header`；其次 `cookie`、`local-storage`、`session-storage`；只有页面本身要求时才用 `query`。
2. 确认页面稳定条件。已知稳定锚点时传 `--wait-selector`；否则使用 `--wait-until load` 并设置 `--settle-ms`。
3. 确认抓取范围。若未指定模块，默认抓取整页业务范围；若已指定模块，优先通过 `--scope-selector` 或业务区域限定只更新该模块。
4. 默认使用 `--capture-mode business`。只有用户明确要求更宽泛的交互元素时才改为 `interactive`，要求全量可见 DOM 时才改为 `all`。
5. 不要在聊天中回显 token。优先使用环境变量 `CAPTURE_TOKEN`，再通过 `--token-env` 传入脚本。
6. 需要 YAML 时优先使用 `--export-locator-yaml`。`--export-uiproject-yaml` 只是兼容别名，也会输出 v2 分层 YAML。
7. 只输出页面实际存在的区域。不要因为模板约定就强行输出 `team_panel`、`modals` 等空区域。
8. 非列表/非表格列元素的定位策略必须保证唯一匹配。不要把 `.el-input__inner`、`.el-select__input`、`.el-range-input`、动态 `el-id-*`、绝对 XPath 当作主定位。
9. Playwright 场景下，优先使用语义定位。推荐顺序：`test_id` > `role` > `label` > `placeholder` > 唯一文本锚点 > 唯一相对 XPath/CSS。表格行、表格列、行内操作是允许多元素集合定位的例外。
10. 未指定模块时，除默认静态控件外，还应尽量覆盖可触发业务动态区域的入口元素，例如“新增”“编辑”“设置角色”“更多”“展开”“下拉箭头”等。
11. 对自定义触发器不要只依赖原生标签。若元素具备清晰业务文本、图标+文本组合、业务容器常见类名、`cursor:pointer` 或明显的点击语义，也应纳入候选。
12. 对重复文本或重复 placeholder，不要在抓取阶段去重成单个元素；应完整保留，并把后续按区域拆分的责任交给 `analyze-business-components`。

## 执行

主页面捕获：

```powershell
$env:CAPTURE_TOKEN="..."
python .\scripts\capture_elements.py `
  --url "https://example.com/app" `
  --auth-mode local-storage `
  --auth-key access_token `
  --token-env CAPTURE_TOKEN `
  --wait-until load `
  --settle-ms 2000 `
  --capture-mode business `
  --save-screenshot `
  --output-dir ".\runs\app-page" `
  --export-locator-yaml ".\runs\app-page\app_page.yaml"
```

点击按钮并捕获弹窗：

```powershell
$env:CAPTURE_TOKEN="..."
python .\scripts\capture_elements.py `
  --url "https://example.com/app" `
  --auth-mode local-storage `
  --auth-key access_token `
  --token-env CAPTURE_TOKEN `
  --wait-until load `
  --settle-ms 2000 `
  --capture-mode business `
  --click-keywords 新增 设置 `
  --capture-modal `
  --output-dir ".\runs\app-modal" `
  --export-locator-yaml ".\runs\app-modal\app_page.yaml"
```

## 关键参数

- `--url`：目标页面地址。
- `--auth-mode`：`none`、`header`、`cookie`、`local-storage`、`session-storage`、`query`。
- `--auth-key`：header 名、cookie 名、storage key 或 query 参数名。
- `--auth-scheme`：header 模式下的前缀，默认 `Bearer`。
- `--token-env`：从环境变量读取 token，优先使用。
- `--wait-until`：`domcontentloaded`、`load`、`networkidle`。
- `--wait-selector`：页面渲染完成的锚点选择器。
- `--capture-mode`：`business`、`interactive` 或 `all`。
- `--scope-selector`：只抓取某个区域。
- `--include-dom-path`：显式输出 `dom_path` 祖先链，默认关闭。
- `--save-screenshot`：保存渲染后的整页截图。
- `--export-locator-yaml`：导出 schema_version=2 分层 locator YAML。
- `--export-uiproject-yaml`：兼容别名，输出同样的 v2 YAML。
- `--click-keywords`：按按钮文本关键词点击目标按钮后再继续抓取。
- `--capture-modal`：点击后捕获打开的弹窗/对话框区域，并写入同一个 YAML 的 `regions.modals`。

## v2 YAML 结构

YAML 顶层使用分层页面模型：

```yaml
schema_version: 2
page:
  key: user_manage
  name: 用户管理
  url: /admin/system-manage/user
regions:
  team_panel: ...
  filters: ...
  toolbar: ...
  table: ...
  modals: ...
```

区域规则：

- `regions.team_panel`：团队管理侧栏区域，包含 `container`、`title`、`actions`、`search` 和 `items`。
- `regions.filters.fields`：筛选区字段，例如 `name_input`、`full_account_input`、`role_select`。
- `regions.toolbar.actions`：工具栏按钮，例如 `add_user_button`、`batch_import_button`、`export_button`。
- `regions.table.collection`：表格行集合，默认用 `.el-table__row`。
- `regions.table.columns`：列单元格相对定位，包含 `column_key`、`header`、`header_strategies`、`cell_strategies`。
- `regions.table.row_actions`：表格行内操作，例如 `edit_button`、`set_role_button`。
- `regions.modals`：点击按钮后出现的弹窗，使用 `opened_by` 关联触发按钮。

普通元素统一包含：

- `description`
- `kind`
- `required`
- `strategies: [{type, path}]`
- `semantic`

普通元素定位约束：

- `strategies` 只保留稳定且可直接用于 Playwright 的候选。
- 非表格元素必须唯一匹配。
- 不要输出仅靠通用 class 才能命中的定位。
- 不要把动态 `id`、绝对 XPath 作为默认主策略。
- `type: role` 的 `path` 允许直接保存 Playwright 表达式，例如 `page.getByRole("button", { name: "搜索" })`。

表格列额外包含：

- `column_key`
- `header`
- `header_strategies`
- `cell_strategies`

弹窗示例：

```yaml
regions:
  modals:
    add_user_modal:
      description: 新增用户
      kind: modal
      opened_by: add_user_button
      container:
        strategies: [{type: xpath, path: "//div[contains(@class, 'el-dialog')]"}]
      fields:
        name_input:
          strategies: [{type: placeholder, path: 请输入姓名}]
      actions:
        confirm_button:
          strategies: [{type: text, path: 确定}]
```

## 输出文件

脚本会在输出目录生成：

- `summary.json`：抓取参数、页面信息、统计信息、产物路径。
- `elements.json`：完整元素数组。
- `elements.ndjson`：逐行 JSON，适合脚本二次处理。
- `page.png`：仅在传入 `--save-screenshot` 时生成。
- `*.yaml`：仅在传入 `--export-locator-yaml` 或 `--export-uiproject-yaml` 时生成。

## 完成后的回复

- 不要回显 token。
- 不要贴完整 `elements.json`。
- 只汇报页面标题、最终 URL、抓取元素数量、输出目录、YAML 路径、截图路径和主要异常。
