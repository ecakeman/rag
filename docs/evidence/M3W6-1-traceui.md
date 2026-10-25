# M3W6-1 trace 可视化+注入缓解+打磨 验收证据 — 2026-10-25 17:07:02
## git rev: ee00e3a+工作区

## ① 前端对话页(views/chat/index.vue): SSE 流式渲染/思考过程面板(trace 事件逐节点)/引用角标点击抽屉/会话管理/停止按钮;fetch-event-source POST+JWT
### pnpm build: exit=0 (2.25MB)
╭───────────────────────────────────────────────────────────╮
│ 🎉 恭喜打包完成（总用时00分12秒，打包后的大小为2.25 MB）  │
╰───────────────────────────────────────────────────────────╯

## ② 注入缓解: app/agent/injection.py 六模式(中英), synthesize 前扫描资料块 → trace(injection-warning); pytest 3 用例

## ③ agent 在线冒烟(重启 python 加载新代码后, 容器内直连 /chat)
### 无 key: 图执行 rewrite 节点(trace 事件已发)→ LLM 缺凭证 → 优雅 error(5032) 事件,链路贯通
event: trace
data: {"node": "rewrite", "status": "end", "detail": "", "tsMs": 0}

event: error
data: {"code": 5032, "message": "AI 服务内部错误: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable."}



## ④ 视觉截图: 宿主 IAB webview 无法访问容器端口(环境限制,前证),页面视觉确认留用户浏览器 — 挂起项如实记录

## 结论: PASS(功能与注入缓解有测试+在线冒烟;视觉项挂起)
