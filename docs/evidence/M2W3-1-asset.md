# M2W3-1 资产管理基座 验收证据 — 2026-10-25 16:33:15
## git rev: e649e86+工作区

## ① pytest -q(容器内,新增 11 用例)
exit=0
.............................                                            [100%]
29 passed in 1.58s

## PROMPT_PACK 当前值:
826b32d9

## ② llm_call 观测(单测内以 fake-model 真写真实 PG 后清理;这里展示写入能力由测试断言覆盖)
### 覆盖点: 重试矩阵(5xx重试2次/4xx不重试)/json_object探测400摘除/解析降级fenced剥离/PROMPT_PACK变化与复原 — 全部有专属断言(test_llm.py 5用例+test_prompts.py 6用例)

## 结论: PASS(29 用例全绿,验收卡 ① 全项)
