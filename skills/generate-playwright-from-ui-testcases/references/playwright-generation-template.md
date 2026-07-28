# Playwright 脚本生成模板

仅在生成代码前作为参考使用；不要把模板说明直接复制进最终脚本。

## 标准目录

默认页面级脚本目录：

```text
automation/playwright/<page_or_module>/
  <page>_page.py
  state_setup.py
  test_<page>_smoke.py
  test_<page>_readonly.py
  test_<page>_write.py
  test_<page>_role.py
```

## 文件职责

- `<page>_page.py`
  只封装页面元素和页面动作，不写业务断言。
- `state_setup.py`
  只负责登录、进入页面、切换页面状态、结果文件路径和公共辅助方法。
- `test_<page>_smoke.py`
  放页面可达、核心区域展示、关键弹窗可打开这类冒烟场景。
- `test_<page>_readonly.py`
  放筛选、分页、展示、默认选中、只读字段、必填提示等不改数据场景。
- `test_<page>_write.py`
  放新增、编辑、删除、状态切换、取消关联等会修改业务数据的场景。
- `test_<page>_role.py`
  放多角色账号、入口权限、按钮权限和无权限断言。

## 写保护规则

- `test_<page>_write.py` 默认必须有显式开关，例如 `YSP_ALLOW_<PAGE>_WRITE=1`。
- 未设置开关时，可以输出 `BLOCKED` 或直接跳过，但不要静默写数据。
- 若真实写入后需要清理，优先在代码中提供清理函数；若还需 SQL 方案，则同时生成备份/执行/回滚 SQL。

## 不要这样拆

- 不要为 `validation`、`submit`、`toggle`、`unbind`、`filters` 各自单独建文件，除非页面已复杂到难以维护。
- 不要把“脚本执行结果 JSON”“截图目录”“报告 Markdown”当成生成阶段默认输出。
- 不要在 `Page Object` 里混入测试用例断言。
