# AGENTS.md

## Skill 修改落点规则

1. 修改本仓库任一 Skill、模板、插件清单或规则文件前，必须先定位真实源目录、Git 主仓或当前功能分支对应的 worktree，并先在真实仓库内执行 `git status`。
2. `C:\Users\Administrator\.codex\plugins\cache\`、`C:\Users\Administrator\.codex\plugins\cache-backup\` 等缓存目录只用于安装、运行和回放，不得作为唯一修改目标。
3. 若为了立即验证当前安装实例需要同步缓存，必须先修改真实源目录或分支，再执行重新安装、同步或缓存刷新；最终交付和提交范围以真实源仓库的 Diff 为准。
4. 若当前只定位到缓存目录，必须继续追溯对应的 Git 主仓、功能分支或 worktree；在未找到真实源落点前，不得把缓存编辑视为完成。
5. 除非用户明确要求仅做临时缓存验证，否则不得只改缓存目录而不回写真实源目录或分支。
