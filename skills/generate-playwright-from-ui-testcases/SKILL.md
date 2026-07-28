---
name: generate-playwright-from-ui-testcases
description: 将标准 UI 自动化测试用例 Markdown 与已验证定位资产转换为 Playwright Python 代码资产，包括 Page Object、state setup、`test_*_smoke.py`、`test_*_readonly.py`、`test_*_write.py` 和可选的 `test_*_role.py`。适用于用户已经完成测试点整理与定位校验，下一步需要把用例落成 Playwright 脚本，但不希望默认执行脚本、截图或生成测试报告的场景。
---

# 生成 Playwright 脚本

使用本 Skill 时，只负责生成 Playwright 代码资产，不默认执行脚本，不默认产出执行结果 JSON、截图或测试报告。

## 输入前提

至少确认以下输入：

1. 标准 UI 自动化测试用例文件路径，例如 `testcases/*UI自动化测试用例.md`。
2. 已验证定位资产路径，例如 `final-locators.json`、Page Object 基线或校验通过的 locator 结果。
3. 目标项目目录和输出目录；默认优先写入项目 `automation/playwright`。
4. 目标页面或模块范围；若用户只要求一个页面，禁止顺手扩展整个系统。

若缺少定位资产、页面 URL、登录方式或测试用例仍停留在测试点层，不要硬生成脚本；应先回退到上游 Skill。

## 何时读取参考模板

开始生成代码前，读取：

- [playwright-generation-template.md](references/playwright-generation-template.md)

只有在需要确认目录结构、命名规范、拆分策略或写保护规则时再读取，不要把参考模板全文复制进最终代码。

## 生成流程

1. 先确认测试用例已经是“标准 UI 自动化测试用例”，而不是原始测试点。
2. 识别页面是否已有可复用的 Page Object 或 state setup；已有时优先增量更新。
3. 将同一页面脚本按以下固定结构拆分：
   - `test_<page>_smoke.py`
   - `test_<page>_readonly.py`
   - `test_<page>_write.py`
   - `test_<page>_role.py`（仅在存在角色差异或后续明确需要时生成）
4. 将只读场景统一并入 `readonly`，包括展示、筛选、分页、默认选中、弹窗打开、表单必填提示和只读字段校验。
5. 将所有会修改业务数据的场景统一并入 `write`，包括新增、编辑、删除、切换状态、取消关联和批量操作。
6. 为 `write` 脚本默认加显式写保护开关；只有用户明确允许，才真正执行写入。
7. 若脚本内会真实写入数据，必须一并生成清理或回滚策略，但这类策略仍属于代码资产，不属于执行报告。

## 输出规则

- 默认输出这些代码资产：
  - `<page>_page.py` 或业务化命名的 Page Object
  - `state_setup.py`
  - `test_<page>_smoke.py`
  - `test_<page>_readonly.py`
  - `test_<page>_write.py`
  - `test_<page>_role.py`（可选）
- 默认使用 Playwright Python。
- 默认不生成执行结果 JSON、截图目录、测试报告或 `reports/index.md` 更新。
- 只有当用户明确要求“顺便执行验证”时，才进入执行与报告阶段。

## 拆分规范

- 一个页面通常控制在 3 到 5 个 `test_*.py`。
- 不要按每个按钮、每个测试点、每个弹窗单独拆文件。
- 不要把 `tag_group`、`toggle`、`unbind` 这类动作类型拆成额外文件，除非它们已经演化成独立业务子页面。
- `role` 脚本默认只承接多角色账号、入口权限、按钮权限和无权限断言；若当前项目没有角色矩阵，允许生成骨架并在代码中显式说明前置缺失。

## 生成边界

- 本 Skill 负责“代码生成”，不负责“执行验证”。
- 本 Skill 可以在代码里生成写保护开关、清理函数或回滚函数，但不默认调用它们。
- 本 Skill 不要默认生成报告 Markdown、HTML、JSON；这些属于后续执行阶段产物。

## 最终回复

至少汇报：

1. 消费了哪些输入文件。
2. 生成了哪些代码资产。
3. 当前页面最终拆成几个 `test_*.py`，为什么这样拆。
4. 哪些脚本默认安全可跑，哪些脚本带写保护。
5. 是否仍缺角色矩阵、定位资产或写入回滚前提。
