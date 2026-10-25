# M1W1-2 Java 骨架 验收证据 — 2026-10-25 15:37:16
## git rev: 827fd93+工作区

## ① ./mvnw test(修复 InternalTokenFilter 编译错 + 测试超时参数后)
### exit code + surefire 汇总
mvn-exit=0
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 7.365 s -- in com.enterprise.docqa.BackendApplicationTests
Tests run: 4, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 3.461 s -- in com.enterprise.docqa.ingestion.CallbackFlowTest
Tests run: 6, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.290 s -- in com.enterprise.docqa.ingestion.IngestClientTest
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1.151 s -- in com.enterprise.docqa.ingestion.ReconcileJobTest
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.668 s -- in com.enterprise.docqa.security.AuthIntegrationTest

## ② 登录成功
{"code":0,"message":"ok","data":{"token":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJBRE1JT...
## ③ 带token访问受保护接口
{"code":0,"message":"ok","data":{"records":[],"total":0}}
## ④ 无token 401
401
## ⑤ 错误密码 401
401
## ⑥ swagger
200

## 结论: 通过标准 6/6 ✔(测试 21 全绿含 AuthIntegrationTest 5 用例)
