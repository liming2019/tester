# UI Locator Shared Guidelines

这份共享说明是 6 个 UI 定位 Skill 的软规则层。编排或执行任一阶段时，先按这里的命名、优先级和状态约定工作，再读取对应的 schema。

## 读取顺序

- `capture-web-runtime`：先读 `runtime-capture.schema.json`，再读“状态命名”“异常记录”。
- `analyze-business-components`：再读 `page-model.schema.json`。
- `generate-locator-candidates`：再读 `locator-candidate.schema.json`。
- `validate-locator-stability`：再读 `locator-validation.schema.json`。
- `generate-automation-assets`：至少读 `page-model.schema.json` 和 `locator-validation.schema.json`。
- 若目标是最终自动化资产，`generate-automation-assets` 还应读取 `runtime-capture.schema.json`，确认登录态和状态切换前提。
- `ui-locator-orchestrator`：在拆分任务或审查产物时，按上面顺序决定下游 Skill 该读什么。

## 命名约定

- `page.key` 使用 `snake_case`，例如 `user_manage`、`order_detail`。
- `region` 优先使用固定键：`filters`、`toolbar`、`table`、`pagination`、`modals`、`drawer`、`tabs`、`tree`、`summary`。
- 元素键采用“业务名 + 控件后缀”，例如 `keyword_input`、`search_button`、`status_select`、`confirm_button`。
- 表格行内操作使用动作后缀，例如 `edit_button`、`delete_button`。
- 同名元素必须带作用域，不要在多个区域都出现同一个裸键名。

## 抓取范围规则

- 未指定模块时，默认抓取全页面范围内可见、可操作元素，以及业务动态操作元素。
- 业务动态操作元素包括但不限于：打开弹窗、抽屉、下拉、级联、菜单、表格行操作、树展开、团队面板行操作的触发入口。
- 自定义触发器也属于业务动态操作元素，例如 `div.add`、图标+文字入口、标题栏操作入口、可点击的业务文本块。
- 指定模块时，只更新该模块及其直接触发的业务动态区域，不默认刷新全页面其他模块。
- “指定模块”可以通过区域名、业务名称、模块选择器、页面分区或明确动作来表达，例如“筛选区”“工具栏”“新增用户弹窗”“表格首行操作”。
- 若请求是“更新已有页面资产”，未指定模块时默认刷新整页；指定模块时默认执行增量更新。
- 未指定模块时，“抓取全部”包含两层：默认态业务元素，以及安全动态入口展开后的内部元素。
- 安全动态入口默认可以展开但不提交，例如：打开弹窗、抽屉、下拉、级联面板、行内菜单；保存、确认删除、提交写操作不属于默认可执行范围。
- 重复文本、重复 placeholder、重复按钮名在抓取阶段不得合并；应在建模阶段按区域或状态作用域拆分。

## 运行态材料包约定

`capture-web-runtime` 默认输出材料包，结构以 `runtime-capture.schema.json` 为硬约定，最少要包含：

- `summary.json`
  - `page_title`
  - `final_url`
  - `capture_mode`
  - `states`
  - `anomalies`
- `screenshots/`
  - 默认态截图
  - 每个关键状态至少一张截图
- `snapshots/`
  - DOM、结构化元素、a11y 摘要中的至少一种
- `events.json`
  - 每个状态由什么动作触发
  - 等待条件
  - 抓取时机

若页面存在 iframe、shadow DOM、portal、虚拟列表、懒加载，必须写进 `anomalies`。

建议把 `summary.json` 作为 runtime manifest，本身就满足 `runtime-capture.schema.json`。

## 状态命名

- 默认态使用 `default`。
- 搜索或筛选后使用 `searched`。
- 弹窗打开后使用 `<action>_modal_opened`，例如 `add_modal_opened`。
- 抽屉打开后使用 `<action>_drawer_opened`。
- 切换标签页使用 `<tab_key>_tab_active`。
- 翻页后使用 `page_<n>`。

不要把状态名写成自然语言长句。

## 定位优先级

固定优先级：

1. `test_id`
2. `role`
3. `label`
4. `placeholder`
5. 唯一文本锚点
6. 唯一相对 CSS 或 XPath

禁止把以下内容当默认主策略：

- 通用 class
- 动态 id
- 绝对 XPath
- 深层级 CSS
- 纯视觉顺序定位

## 风险标签

- `fragile`
  含义：当前能工作，但明显容易因结构变化失效。
- `text-duplicate-risk`
  含义：依赖文本，且同页或跨状态可能重复。
- `dynamic-attribute`
  含义：依赖动态 id、运行时 class 或随机属性。
- `state-dependent`
  含义：只在特定状态下成立。
- `i18n-sensitive`
  含义：语言切换后可能失效。
- `needs-testability-contract`
  含义：当前页面缺少稳定锚点，建议前端补测试属性。

## 校验状态

- `PASS`
  唯一、可见、可操作，且在声明适用的状态下稳定。
- `WARN`
  当前可用，但存在明显漂移风险。
- `FAIL`
  非唯一、不可见、不可操作，或跨状态直接失效。
- `BLOCKED`
  由于权限、数据、环境或页面异常暂时无法完成有效校验。

`WARN` 不要自动升级为最终默认定位。

## 自动化资产交付约定

若任务目标是后续直接写 UI 自动化，最终交付默认应包含：

1. `final_locators.json` 或 `final_locators.yaml`
2. `Page Object`
3. `state helpers`
4. `smoke case`

说明：

- `PASS` 作为主定位进入最终资产。
- `WARN` 只能作为 fallback，并附带风险说明。
- `FAIL/BLOCKED` 禁止进入最终资产。
- 表格行内操作、下拉、级联、弹窗必须方法化，不要只交付裸定位。
- 登录态进入方式必须可追溯到 `runtime manifest`，例如 cookie、header 或 localStorage 注入。

## 何时要求前端补测试锚点

出现以下任一情况时，优先建议补 `data-testid` 或等价属性：

- 同页存在多个同文案按钮，且没有稳定作用域。
- 只能依赖动态 id、深层 XPath 或通用 class。
- 表格、树、虚拟列表的行内操作无法稳定定位。
- 弹窗和页面本体控件文本完全重叠，且容器范围不稳定。
- 同一元素在多语言、权限差异或重构后高概率漂移。
