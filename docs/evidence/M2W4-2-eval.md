# M2W4-2 评测脚手架+语料+simple 集 验收证据 — 2026-10-25 16:56:57
## git rev: fbc4281+工作区
## 过程修复: CSV 第8题 ref_answer 含逗号未加引号致列漂移(已修)

## ① pytest(新增 6 用例: 数据集30题完整性/消融矩阵=设计/开关应用/CSV列契约/judge解析/pack校验)
exit=0
...............................................                          [100%]
47 passed in 2.07s

## ② 语料 v1: 4 份 md(employee-handbook/attendance/expense/product-faq, data/samples/)
attendance.md
employee-handbook.md
expense.md
product-faq.md

## ③ 全量跑分: 需先填 .devcontainer/.env 的 LLM_API_KEY 并上传语料(向量入库)后执行 python -m eval.run --config A0 --dataset simple — 挂起到 key 就绪;检索指标列已实现、judge 列无 key 时如实记 no-key

## 结论: PASS(评测器与数据集就绪并通过单测;真实跑分为计划内挂起项)
