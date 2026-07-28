# 直连迁移 HTML 报告设计原则

本参考用于说明直连迁移报告为什么这样设计。正常生成报告时优先执行脚本和 contract，不必加载本文件。

## 调研来源

- AWS Database Migration Service Data Validation：https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Validating.html
  强调源目标记录级验证、验证状态、失败记录和验证期间的限制。
- AWS DMS Best Practices：https://docs.aws.amazon.com/dms/latest/userguide/CHAP_BestPractices.html
  建议迁移期间启用数据验证，目标是确认数据准确迁移到目标端。
- Google Cloud Spanner migration validation example：https://docs.cloud.google.com/spanner/docs/non-relational/migrate-from-cassandra-to-spanner
  明确把源目标表行数对比作为一种迁移验证方式。
- Microsoft SQL Server replication validation：https://learn.microsoft.com/en-us/sql/relational-databases/replication/validate-data-at-the-subscriber
  使用 row count 或 checksum 在发布端和订阅端之间做一致性比较。
- Databricks Lakeflow expectations：https://docs.databricks.com/aws/en/ldp/expectations
  强调把数据质量约束显式化，并输出质量指标。
- Databricks validation overview：https://docs.databricks.com/aws/en/transform/validate
  覆盖 schema enforcement、table constraints、expectations、monitoring 和自定义业务逻辑。

## 抽象后的共性

1. 报告先回答是否可验，再回答是否通过。
   缺少源基线、目标来源、业务键、权限或字段规则时，应判定 BLOCKED 或 WARN，不应伪装成 PASS。

2. 完整性和准确性分开。
   总量一致只能证明范围可能一致，不能证明字段准确；字段准确也不能替代缺失/额外/重复检查。

3. 业务键是迁移报告的中心。
   任何源目标对账都必须说明匹配键、唯一性假设、重复情况和歧义风险。

4. 差异要分组。
   至少区分源有目标无、目标有源无、目标重复、字段值不一致、文件/对象不可用、规则缺失、前置阻塞。

5. 质量规则必须可追溯。
   字段准确性表要展示预期规则、实际核验规则、检查记录数、不匹配记录数和状态。

6. 覆盖缺口不能写成 0。
   没有独立核验的范围必须进入覆盖缺口，而不是写到差异表里做 0 差异。

7. 报告要支持复跑。
   需要记录数据范围、抽取时间、源目标过滤条件、批次/快照时间、脚本版本和复跑前置。

8. 主报告面向决策。
   首页展示结论、范围、核心统计、差异和复跑动作；长字段明细、样例和原始证据放到附录或证据页。

## 直连迁移报告固定维度

- 执行摘要：总体状态、是否可验、是否需要修复或复跑。
- 范围口径：平台、店铺/账号、日期、环境、数据源过滤条件。
- 源基线：源接口/源库/源文件、请求或查询参数、源记录数、源抽取时间。
- 目标来源：目标库/接口/文件、目标查询条件、目标记录数、目标快照时间。
- 业务键：匹配键、唯一性、重复、歧义和替代键。
- 完整性：源行数、目标行数、源有目标无、目标有源无、目标重复、覆盖率。
- 准确性：字段规则、检查记录数、不匹配数、关键字段状态。
- 差异与阻塞：差异分组、样例、影响范围、阻塞原因。
- 覆盖缺口：未全量、未逐字段、仅抽样、缺权限、缺基线等。
- 整改与复跑：修复动作、补证动作、复跑条件、优先级。

## 不采用 staged 报告结构的原因

直连迁移没有必须展示的阶段一、阶段二和中间层证据。强行套 staged 结构会造成：

- 报告里出现不存在的中间层。
- 结论读者误以为链路经过 ODS/DWD 或映射表。
- 覆盖缺口被错误归入阶段差异。

因此直连报告按“源证据 -> 目标证据 -> 业务键 -> 完整性 -> 准确性 -> 差异/风险 -> 复跑动作”的顺序组织。
