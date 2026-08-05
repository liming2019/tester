# 测试报告目录

本目录只保留当前结论入口和已确认长期纳管的正式报告，避免历史执行报告、明细 HTML、完整 JSON 证据和多轮 rerun 产物继续堆积。

默认保留：

- `current.md`：版本级当前有效测试结论和风险入口，固定一个版本一条记录。
- `final/`：已确认需要长期纳管的最终报告包。

默认不保留：

- 普通历史主报告。
- 普通 `details/` 明细报告。
- 完整逐项 JSON 证据。
- 多轮 rerun、临时诊断、历史修补报告。

正式报告包进入 `final/` 后，必须运行：

```powershell
python automation/validate_report_package.py --report-dir .\reports\final\<正式报告包目录>
```
