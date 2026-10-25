# M2W4-1 A0 问答链路 验收证据 — 2026-10-25 16:53:37
## git rev: 77fb37d+工作区
## 过程修复: ① SSE 的 ASYNC dispatch 被 Spring Security 拦(补 dispatcherTypeMatchers(ASYNC).permitAll) ② onCompletion 自中断竞态(改温和取消:关流+cancel(false)) ③ meta 事件先于异步流由 SseEmitter 早期缓冲保证顺序

## ① Java ./mvnw test 全绿(23 用例)
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 8.620 s -- in com.enterprise.docqa.BackendApplicationTests
Tests run: 2, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 7.073 s -- in com.enterprise.docqa.chat.ChatFlowIntegrationTest
Tests run: 4, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 3.896 s -- in com.enterprise.docqa.ingestion.CallbackFlowTest
Tests run: 6, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.224 s -- in com.enterprise.docqa.ingestion.IngestClientTest
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1.003 s -- in com.enterprise.docqa.ingestion.ReconcileJobTest
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.487 s -- in com.enterprise.docqa.security.AuthIntegrationTest

## ② Python pytest 全绿(41 用例,含 A0 流事件序列/拒答/引用过滤/异常 4 用例)
exit=0

## ③ 断连不落库: clientDisconnect_noAssistantRow 通过(§8.4 语义,仅 user 行)

## ④ 真实 LLM 冒烟: 待 LLM_API_KEY(M2W4-2/M4 补);当前无 key 链路到 embedding/LLM 调用层即正确报错并可观测

## 结论: PASS(单测+集成 64 用例全绿;SSE 六类事件在透传链路顺序正确;断连语义验证)
