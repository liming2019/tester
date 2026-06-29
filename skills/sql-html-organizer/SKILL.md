---
name: sql-html-organizer
description: Organize batches of SQL into a local HTML summary manager with duplicate detection, business-page-first categorization, drag-sort support, and optional local save-service setup. Use when Codex must collect many SQL statements, classify them by real product page or module instead of table names, append them into an existing HTML SQL hub, rebuild a broken/garbled SQL hub, deduplicate repeated SQL entries, or create/start a local save-server so edits can be written back to the current HTML file directly.
---

# SQL HTML Organizer

## Purpose

Use this skill to maintain a local SQL knowledge base as an editable HTML manager.

Default goal:
- store SQL in one or more local HTML summary pages
- classify by real business page structure first
- detect duplicates before appending
- keep the page directly editable
- support direct save back to the current HTML file through a local save service

This skill is for local knowledge organization, not for executing SQL against databases unless the user explicitly asks for that separately.

## Default Structure

Prefer business-page-first grouping over technical grouping.

Bad default grouping:
- media table
- tag table
- cost table

Preferred grouping:
- 素材列表
- 素材详情页
- 成片列表
- 成片详情页
- 被引用分析
- 分类与标签配置
- 合集相关
- 个人中心/统计

If the user gives a real product menu or screenshot, follow that structure over any inferred structure.

## Required Workflow

1. Inspect the current target HTML summary file if it exists.
2. Determine whether the file is healthy:
   - if layout or script is broken
   - if content is garbled because of encoding problems
   - if save logic is unusable
   - rebuild instead of patching repeatedly
3. Parse the incoming SQL batch into entries:
   - title from comments if present
   - otherwise create a short business-readable name
   - add a concise summary
   - add a detail description
4. Detect duplicates before insertion:
   - exact same title + same SQL: keep one only
   - same title but different SQL: treat as variant and rename if needed
   - same SQL text with minor whitespace/comment differences: prefer existing entry unless the new one is clearly a better version
5. Classify each SQL entry:
   - first by real page/module
   - second by functional area inside that page if needed
6. Update the HTML manager:
   - preserve existing entries unless the user asked to replace or delete
   - append non-duplicate entries to the correct module
   - keep item order stable unless the user requests resorting
7. Ensure the HTML supports:
   - left directory
   - middle SQL list
   - right detail/SQL editor
   - save back to file
   - drag sorting if already required by the user
8. If direct file save is required, create or maintain a local `save-server.py` and ensure the HTML posts to the correct localhost port.
9. After edits, verify:
   - target files exist
   - save endpoint port is reachable if a save server is expected
   - user-visible strings are not garbled

## Duplicate Handling Rules

Apply these in order:

1. Exact duplicate:
   - same title
   - same SQL after trimming whitespace
   - do not add again

2. Same business intent, different formatting only:
   - normalize whitespace
   - ignore repeated inline comments when they do not change meaning
   - keep the existing item unless the new one is cleaner

3. Same title, different SQL:
   - do not overwrite silently
   - keep both only if they are clearly different variants, scopes, or dates
   - rename one side using a suffix such as:
     - `-明细`
     - `-汇总`
     - `-按用户`
     - `-按视频`
     - `-数据面板`

4. Same SQL, different titles:
   - prefer the clearer business-facing title

Always tell the user briefly whether items were appended, merged, skipped as duplicates, or rebuilt into a new structure.

## Rebuild Rules

Rebuild the HTML instead of incremental patching when any of these are true:
- the HTML has repeated encoding corruption
- the front-end script is half-broken
- patching becomes riskier than replacement
- layout requirements changed significantly

When rebuilding:
- keep the target file path unchanged unless the user asks for a new file
- preserve existing SQL entries by carrying their data into a clean JSON data block
- rebuild the UI around that data block

## Save Service Rules

When the user wants edits to save directly back into the current HTML file:
- do not rely on browser localStorage as the main persistence method
- create or maintain a local `save-server.py`
- bind the HTML page to that localhost port
- verify the port is reachable after launch

Recommended behavior:
- page save button posts `{ html: ... }` to `http://127.0.0.1:<port>/save`
- the service writes UTF-8 text back to the target HTML path
- reset saved status text in the persisted HTML to a clean default such as `状态：未修改`

If the local save service is unavailable, the page may fall back to export, but direct-save should remain the preferred path when the user asked for it.

## UI Rules

Default SQL hub UI should stay pragmatic:
- left: directory tree
- middle: SQL item list
- right: description + SQL editor

Prefer:
- short item names in the middle list
- no repeated long description text in the middle list unless requested
- right panel title linked to the selected middle item
- compact editing experience

If the user asks for drag sorting:
- enable drag sorting on the middle SQL list
- reorder the in-memory item array
- require save to persist order into the HTML file

## Bundled File Expectations

This skill is intentionally lightweight.

Recommended companion files when expanded later:
- `references/page-structure-template.md`
- `references/dedup-rules.md`
- `scripts/rebuild_sql_hub.py`
- `scripts/check_save_server.ps1`

For now, follow the workflow in this SKILL.md directly.

## Output Expectations

When using this skill in a task, report only the essentials:
- target HTML path
- whether SQL were appended, skipped, merged, or reorganized
- whether duplicates were found
- whether a save service was started or repaired
- anything still broken
