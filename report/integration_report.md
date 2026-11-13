# 集成验证报告

> 运行：`python3 tools/verify_integration.py`（用 AST 抽取改动函数在最小环境执行，无需 PyQt5）

| 验证项 | 结果 | 细节 |
|---|---|---|
| evaluate_recordings 返回结构兼容原 UI | ✅ 通过 | keys=['partA', 'partB_five', 'partB_three', 'partC'] |
| score_report 含卷面/折算/档次 | ✅ 通过 | 卷面 24.96807692307692/60 → 折算 8/20，B 档 |
| 在线识别来源被记录 | ✅ 通过 | online_used=True |
| 字段类型可直接喂给 _eval_total_score | ✅ 通过 | accuracy=0.0129, sem=0.9462 |
| 未作答记 0 分 | ✅ 通过 | paper=0.0（原算法全空会白送 8 分） |
| 题库加载不再 extractall 整包 | ✅ 通过 | data.json 已解析（9 个顶层键）；临时目录解压文件数=0 |
| 题库数据可被评分引擎消费 | ✅ 通过 | 要点 15 条 |

## 说明

- `app/SoloTalk_optimized.py` 由 `tools/apply_optimizations.py` 从原始 7626 行源码生成，仅替换 4 处（import / BGE 停用 / 评分函数 / 题库解压）+ 1 处注释，其余 UI 与流程代码保持不变。
- `evaluate_recordings` 的返回字典结构与原实现完全一致，因此 `_eval_total_score()`、历史记录、结果卡片无需任何改动；新增的 `score_report` 字段旧 UI 会自然忽略。
- 差异全文见 `app/solotalk_patch.diff`。
