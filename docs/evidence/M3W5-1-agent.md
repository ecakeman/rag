# M3W5-1 LangGraph Agent 验收证据 — 2026-10-25 17:02:17
## git rev: adc523d+工作区

## ① pytest(新增 9 用例)
exit=0
........................................................                 [100%]
56 passed in 2.47s

## 覆盖场景
- SIMPLE 全节点序列: rewrite→router→retrieve→rerank→grade→synthesize→verify(断言精确执行序)
- CHITCHAT 跳过检索与生成 LLM
- COMPLEX 两跳后 ENOUGH(retrieve×2, 引用2条)
- MAX_HOPS 封顶(retrieve==3)
- 连续零新增即停(retrieve==2 不进第三跳)
- 零命中拒答模板且不调 synth
- verify FAIL→synthesize 重试1次→PASS
- verify 连续 FAIL→尾部附人工复核声明
- router 每轮重置 hits/hop(状态无残留,§7.4)

## ② 时间旅行/checkpointer: 依赖真实 PG+llm;checkpointer 接线为可选注入(graph.build_graph 未挂),作为答辩演示项在 M4 补接 — 如实记录

## 结论: PASS(56 用例全绿;§8.2 全部边/终止条件/降级路径有断言)
