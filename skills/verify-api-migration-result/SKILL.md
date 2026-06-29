---
name: verify-api-migration-result
description: Verify API-based data migration results after a migration has already been executed. Use when the user asks to check whether migrated data is accurate across source baseline data, target database, target open APIs, object storage such as MinIO, files, ID mappings, master data, relationship data, or to generate Chinese HTML migration verification reports. This skill is for result verification only, not for executing migration writes.
---

# Verify Api Migration Result

This skill verifies results of an API-driven migration. It must not perform migration writes or modify source/target data.

## Scope

Use this skill for result accuracy checks such as:

- Source baseline data versus target system result data.
- API-imported records verified through target database, open API query, and object storage.
- Organization, users, categories, tags, status, media master data, files, and relationship data.
- Chinese HTML reports with missing, extra, duplicate, field-difference, relationship-difference, and file-availability findings.

Do not use this skill for pure database table-to-table synchronization checks. Use `verify-db-sync-result` for that narrower case.

## Mandatory Confirmation

Before giving any final pass/fail conclusion, confirm numeric comparison rules with the user:

`金额字段是否允许四舍五入？如果允许，请告知保留几位小数；比率字段是否也按同样规则处理？`

If the user has not confirmed this, build tools, inspect structure, or prepare reports, but do not issue a final pass/fail conclusion.

## Verification Workflow

Execute in this order. Do not skip steps.

1. Read migration scope and API documentation.
2. Confirm source baseline source: source database, CSV, Excel, JSON, SQL export, or a mixed baseline.
3. Confirm target verification sources: target database, target open API, MinIO/object storage, file URL checks, or page sampling.
4. Confirm business keys and source-to-target ID mapping strategy.
5. Discover/read source and target structures.
6. Build field mappings using user rules first, then comments/semantic names, then field names.
7. Verify total counts.
8. Verify unique record counts and duplicates.
9. Verify field values record by record using business keys or mapping keys.
10. Verify relationship data, including parent-child, ownership, binding, and media reference relations.
11. Verify file results: address existence, URL accessibility, size, duration, cover, original/transcoded file availability.
12. Summarize differences and likely causes.
13. Generate Chinese HTML report.
14. Re-read the HTML as UTF-8 and check for garbled Chinese before delivery.

## Business Key Rules

Prefer keys in this order:

1. Stable source ID plus migration mapping table.
2. External ID or third-party ID preserved across migration.
3. Natural business key combination.
4. User-confirmed fallback key.

For media migration, common keys include:

- `source_video_id -> target_video_id`
- `third_id`
- `video_type + video_name + author + create_time`
- `finished_video_id + material_id + start + duration`

If the key may not be unique, report the ambiguity and do not silently use it as a unique key.

## Verification Categories

At minimum, support these result categories when applicable:

- Organization: team, group, account, account-team/group, observer groups.
- Basic configuration: video type/category, tag group, tag item, category-tag binding, content status, default collection.
- Media master data: material, finished video, title, description, author, team, group, category, collection, tags, status, duration, cover, file size, video URL.
- File data: original file, transcoded file, cover file, MinIO path, rewritten target URL, URL accessibility.
- Relationship data: finished video references material, segment start, duration, first segment, cover flag, track index, track attributes.

## Difference Types

Classify differences into:

1. Source exists, target missing.
2. Target exists, source missing.
3. Duplicate target records.
4. Field value mismatch.
5. Relationship mismatch.
6. File missing or inaccessible.
7. Mapping ambiguity or unmapped field.
8. Verification blocked by missing baseline/configuration.

## Field Coverage Checks

When verifying API-to-map-to-database migrations, include a read-only field coverage check whenever the migration stores source API JSON or source snapshots in a mapping table and then writes selected fields into business tables.

Classify field coverage into these buckets:

1. `map有但未配置落业务表`: the source/map JSON field exists, but no business-table target mapping is configured.
2. `仅存map字段未落业务表`: the value is intentionally kept only in the mapping table, such as source business key stored in `view_migration_id_map.old_id`.
3. `业务表无map来源-NULL`: the business-table field has no map/API source and all checked rows are `NULL`.
4. `业务表无map来源-默认值`: the business-table field has no map/API source and is populated by a fixed default value.
5. `业务表无map来源-空串`: the business-table field has no map/API source and all checked rows are empty strings.
6. `业务表无map来源-系统生成/混合`: the business-table field has no map/API source and values are generated by the target system, the migration program, database expressions, or mixed rules.

For field coverage, keep the behavioral distinction clear:

- API-to-map verification proves API fields were captured into the mapping table or snapshot JSON.
- Map-to-database verification proves configured fields were correctly written into business tables.
- Field coverage verification explains fields that are present on one side but are not part of direct value comparison.
- Do not count field coverage warnings as main migration failure unless the user/business rule says the field must be migrated.
- Do not repeat normal mapped fields in the coverage detail when they already passed field consistency verification; show only fields needing attention.

## Report Requirements

Generate a Chinese HTML report. It must include:

1. 核验范围
2. 核验时间
3. 源基准来源和目标核验来源
4. 业务键和ID映射说明
5. 字段映射说明
6. 总量核验结果
7. 唯一性/重复数据核验结果
8. 源有目标无差异表
9. 目标有源无差异表
10. 字段值差异表
11. 关系差异表
12. 文件可用性差异表
13. 概述/总结
14. 结论
15. 失败原因总结

If a section has no differences, keep the summary row but omit detailed rows.

Difference tables must be grouped by difference field/type and show only representative samples by default. Each group should show 1 to 3 samples unless the user explicitly asks for full details.

Each difference sample should include:

- 业务键
- 源主键或源标识
- 目标主键或目标标识
- 差异字段或差异类型
- 源值
- 目标值
- 差异说明

### Field Coverage Report Layout

When field coverage checks are present, place `落库字段覆盖总结` near the top of the report, directly after the title/conclusion block and before the general overview. This section is high priority because it shows whether API/map fields actually reach business tables.

The `落库字段覆盖总结` table must include:

- 模块
- 核验项
- map记录数
- 业务表记录数
- map有未落业务表
- 仅存map未落业务表
- 业务表无map来源-NULL
- 业务表无map来源-默认值
- 业务表无map来源-空串
- 业务表无map来源-系统生成/混合

Each bucket cell must show both count and field names. For example: `7 个` plus the field list. For fields with extra explanation, use one field per line instead of joining everything into one crowded paragraph.

Formatting rules for coverage summary cells:

- `业务表无map来源-默认值`: show the default value after the field name, such as `del_flag（默认值：0）`; if the default is an empty string, show `默认值：空串`; if the default is `NULL`, show `默认值：NULL`.
- `业务表无map来源-系统生成/混合`: show the generation or mixed-value rule after the field name, such as `password（规则：迁移程序写入统一初始化密码密文）`.
- Prefer explicit config notes or confirmed business rules for the `规则`; if inferred from actual values, mark it as an inference and include sample evidence only briefly.
- For default-value and system-generated/mixed columns, render one field per line, with the field name visually distinct from the default/rule text.
- Use readable HTML styling for long coverage cells: field lists, subtle separators, compact text, and horizontal scrolling when the table is wide.

After the summary, include detailed field coverage sections:

- `map JSON字段覆盖情况（仅展示需关注字段）`: source/map JSON field, field description, map-present count, non-empty count, target mapping, coverage conclusion, note.
- `业务表字段来源与默认值情况（仅展示无map来源或非直接映射字段）`: business-table field, field description, map source, configured default, NULL count, empty-string count, default-value count, non-empty count, sample values, coverage conclusion, note.

## File Checks

File verification should be read-only:

- Check target URL is non-empty when source file exists.
- Check HTTP status or object existence when credentials are available.
- Check file size when both source and target sizes are available.
- Check video duration when metadata is available.
- Separate original file, transcoded file, and cover file results.

Do not download large files unless the user explicitly asks or the configured sample limit requires it.

## Failure Cause Summary

When differences exist, analyze likely causes from:

- Migration batch not completed.
- Source-to-target ID mapping error.
- Category/tag/status mapping error.
- Team/group/account ownership mapping error.
- File uploaded but target URL not rewritten.
- Target URL rewritten but file missing in MinIO/object storage.
- Unit conversion error such as seconds versus microseconds.
- API import created duplicate records after rerun.
- Relationship created before referenced media was migrated.
- Field was populated from display text instead of business ID, or the reverse.
- Precision/rounding rule mismatch.

## Safety Rules

- Only run read-only SQL by default: `SELECT`, metadata inspection, and explain-free discovery queries.
- Do not run `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `DROP`, `ALTER`, or migration APIs.
- Mask credentials and sensitive tokens in output.
- Do not include production passwords, tokens, cookies, or MinIO secret keys in reports.
- If user-provided configs include secrets, keep them in config files and do not echo them.

## Delivery Format

Final response must include:

1. 简短结论.
2. HTML 报告路径, if generated.
3. 是否已按用户确认的金额/比率舍入口径判定.
4. 是否存在必须研发修复的问题.
5. Any blocked items caused by missing baseline, mapping, database config, API config, or storage config.

## References

For cloud video manager migration checks, read `references/cloud-video-manager.md` when the request mentions 云视频管家, 素材, 成片, MinIO, 视频导入, or 成片引用素材.
