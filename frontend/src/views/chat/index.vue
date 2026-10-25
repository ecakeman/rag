<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Delete } from "@element-plus/icons-vue";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { http } from "@/utils/http";
import { getToken } from "@/utils/auth";

defineOptions({ name: "Chat" });

marked.setOptions({ gfm: true, breaks: true });

interface Citation {
  no: number;
  chunkId: number;
  docTitle: string;
  sectionPath: string;
  page: number | null;
  text: string;
}

interface TraceItem {
  node: string;
  detail?: string;
}

interface Bubble {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  trace: TraceItem[];
}

interface Session {
  sessionId: number;
  title: string;
}

/** agent 节点中文名（思考过程面板用） */
const TRACE_LABELS: Record<string, string> = {
  rewrite: "问题重写",
  router: "路由分流",
  decompose: "问题分解",
  retrieve: "混合检索",
  rerank: "结果重排",
  grade: "相关性评估",
  reflect: "充分性反思",
  synthesize: "生成回答",
  verify: "答案校验",
  refuse: "拒答"
};

const sessions = ref<Session[]>([]);
const currentSession = ref<number | null>(null);
const bubbles = ref<Bubble[]>([]);
const input = ref("");
const sending = ref(false);
const traceVisible = ref(false);
const drawerCitations = ref<Citation[] | null>(null);
const listEl = ref<HTMLElement>();
let ctrl: AbortController | null = null;

function renderMarkdown(b: Bubble): string {
  if (!b.content) return "";
  const html = DOMPurify.sanitize(marked.parse(b.content) as string);
  // 行内引用标记 [n] 渲染为上标
  return html.replace(
    /\[(\d{1,2})\]/g,
    '<sup class="cite-mark">[$1]</sup>'
  );
}

async function loadSessions() {
  const res = await http.request<{
    code: number;
    data: Session[];
  }>("get", "/api/chat/sessions");
  if (res.code === 0) sessions.value = res.data;
}

async function newSession() {
  const res = await http.request<{
    code: number;
    data: Session;
  }>("post", "/api/chat/sessions", { data: {} });
  if (res.code === 0) {
    sessions.value.unshift(res.data);
    await openSession(res.data.sessionId);
  }
}

async function openSession(id: number) {
  currentSession.value = id;
  bubbles.value = [];
  const res = await http.request<{
    code: number;
    data: {
      id: number;
      role: string;
      content: string;
      citations: Citation[] | null;
      trace: TraceItem[] | null;
    }[];
  }>("get", `/api/chat/sessions/${id}/messages`);
  if (res.code === 0) {
    bubbles.value = res.data.map(m => ({
      role: m.role as "user" | "assistant",
      content: m.content,
      citations: m.citations || [],
      trace: m.trace || []
    }));
    nextTick(scrollBottom);
  }
}

async function deleteSession(id: number) {
  await ElMessageBox.confirm("删除该会话及其全部消息?", "删除会话", {
    type: "warning"
  });
  try {
    const res = await http.request<{ code: number; message: string }>(
      "delete",
      `/api/chat/sessions/${id}`
    );
    if (res.code === 0) {
      sessions.value = sessions.value.filter(s => s.sessionId !== id);
      if (currentSession.value === id) {
        currentSession.value = null;
        bubbles.value = [];
      }
    } else {
      ElMessage.error(res.message || "删除失败");
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || "删除失败");
  }
}

function send() {
  const text = input.value.trim();
  if (!text || sending.value) return;
  if (!currentSession.value) {
    ElMessage.warning("请先新建会话");
    return;
  }
  input.value = "";
  sending.value = true;
  bubbles.value.push({ role: "user", content: text, citations: [], trace: [] });
  const assistant: Bubble = {
    role: "assistant",
    content: "",
    citations: [],
    trace: []
  };
  bubbles.value.push(assistant);

  ctrl = new AbortController();
  fetchEventSource("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken().accessToken}`
    },
    body: JSON.stringify({ sessionId: currentSession.value, message: text }),
    signal: ctrl.signal,
    openWhenHidden: true,
    onmessage(ev) {
      const data = JSON.parse(ev.data || "{}");
      switch (ev.event) {
        case "token":
          assistant.content += data.text;
          break;
        case "trace":
          assistant.trace.push({ node: data.node, detail: data.detail });
          break;
        case "citations":
          assistant.citations = data.items || [];
          break;
        case "done":
          sending.value = false;
          break;
        case "error":
          ElMessage.error(data.message || "AI 服务异常");
          sending.value = false;
          break;
      }
      nextTick(scrollBottom);
    },
    onerror(err) {
      sending.value = false;
      throw err; // 停止重试
    }
  }).catch(() => (sending.value = false));
}

function stop() {
  ctrl?.abort();
  sending.value = false;
}

function scrollBottom() {
  listEl.value?.scrollTo({ top: listEl.value.scrollHeight });
}

onMounted(loadSessions);
onUnmounted(() => ctrl?.abort());
</script>

<template>
  <div class="flex w-full chat-page">
    <!-- 会话列表 -->
    <aside class="w-56 shrink-0 flex flex-col border-r border-gray-200 bg-white">
      <div class="p-3 border-b border-gray-100">
        <el-button type="primary" class="w-full" round @click="newSession">
          新建会话
        </el-button>
      </div>
      <div class="flex-1 overflow-y-auto p-2 space-y-1">
        <div
          v-for="s in sessions"
          :key="s.sessionId"
          class="cursor-pointer rounded-lg px-3 py-2 text-sm flex items-center justify-between group transition-colors"
          :class="
            currentSession === s.sessionId
              ? 'bg-blue-50 text-blue-600 font-medium'
              : 'text-gray-700 hover:bg-gray-50'
          "
          @click="openSession(s.sessionId)"
        >
          <span class="truncate">{{ s.title }}</span>
          <el-icon
            class="shrink-0 ml-2 hidden group-hover:inline-block text-gray-400 hover:text-red-500"
            @click.stop="deleteSession(s.sessionId)"
          >
            <Delete />
          </el-icon>
        </div>
      </div>
    </aside>

    <!-- 对话主区 -->
    <section class="flex-1 min-w-0 flex flex-col bg-white">
      <header
        class="h-12 shrink-0 flex items-center justify-between px-5 border-b border-gray-100"
      >
        <span class="font-semibold text-gray-800">AI 知识问答</span>
        <div class="flex items-center gap-2">
          <span class="text-sm text-gray-500">思考过程</span>
          <el-switch v-model="traceVisible" size="small" />
        </div>
      </header>

      <!-- 消息区 -->
      <main ref="listEl" class="flex-1 overflow-y-auto px-6 py-5">
        <div class="max-w-3xl mx-auto space-y-6">
          <el-empty
            v-if="!bubbles.length"
            description="新建会话后开始提问，回答将附引用出处"
          />

          <template v-for="(b, i) in bubbles" :key="i">
            <!-- 用户消息：右侧气泡 -->
            <div v-if="b.role === 'user'" class="flex justify-end">
              <div
                class="max-w-[75%] rounded-2xl rounded-tr-sm bg-blue-500 text-white px-4 py-2.5 text-sm leading-6 whitespace-pre-wrap break-words"
              >
                {{ b.content }}
              </div>
            </div>

            <!-- AI 消息：左侧头像 + 内容 -->
            <div v-else class="flex gap-3">
              <div
                class="w-8 h-8 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold"
              >
                AI
              </div>
              <div class="flex-1 min-w-0">
                <div
                  v-if="b.content"
                  class="md-body text-sm text-gray-800 leading-7 break-words"
                  v-html="renderMarkdown(b)"
                ></div>
                <div v-else-if="sending" class="text-gray-400 text-sm">
                  <span class="dotting">思考中</span>
                </div>

                <!-- 引用来源 -->
                <div v-if="b.citations.length" class="mt-2 flex flex-wrap gap-1.5">
                  <el-tag
                    v-for="c in b.citations"
                    :key="c.no"
                    size="small"
                    effect="plain"
                    class="cursor-pointer"
                    @click="drawerCitations = b.citations"
                  >
                    [{{ c.no }}] {{ c.docTitle }}
                  </el-tag>
                </div>

                <!-- 思考过程(默认收起，中文节点名) -->
                <el-collapse
                  v-if="traceVisible && b.trace.length"
                  class="trace-collapse mt-2"
                >
                  <el-collapse-item title="思考过程" name="t">
                    <div
                      v-for="(t, k) in b.trace"
                      :key="k"
                      class="flex items-baseline gap-2 text-xs text-gray-500 leading-6"
                    >
                      <el-tag size="small" type="info" effect="plain">
                        {{ TRACE_LABELS[t.node] || t.node }}
                      </el-tag>
                      <span class="break-all">{{ t.detail }}</span>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </template>
        </div>
      </main>

      <!-- 输入区：固定底部 -->
      <footer class="shrink-0 border-t border-gray-100 p-4 bg-white">
        <div class="max-w-3xl mx-auto flex items-end gap-3">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            :disabled="sending"
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            @keydown.enter.exact.prevent="send"
          />
          <el-button v-if="!sending" type="primary" size="large" @click="send">
            发送
          </el-button>
          <el-button v-else type="danger" plain size="large" @click="stop">
            停止
          </el-button>
        </div>
      </footer>
    </section>

    <!-- 引用抽屉 -->
    <el-drawer
      v-model="drawerCitations"
      append-to-body
      title="引用出处"
      size="36%"
    >
      <div v-for="c in drawerCitations || []" :key="c.no" class="mb-5">
        <div class="text-sm font-bold mb-1.5">
          [{{ c.no }}] {{ c.docTitle }}
          <span class="text-xs text-gray-400 font-normal">
            {{ c.sectionPath }}{{ c.page != null ? " · 第" + c.page + "页" : "" }}
          </span>
        </div>
        <div
          class="text-sm text-gray-600 bg-gray-50 rounded-lg p-3 leading-6 whitespace-pre-wrap"
        >
          {{ c.text }}
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.chat-page {
  height: calc(100vh - 98px);
}

/* markdown 正文排版 */
.md-body :deep(p) {
  margin: 0.4em 0;
}
.md-body :deep(ul),
.md-body :deep(ol) {
  padding-left: 1.4em;
  margin: 0.4em 0;
}
.md-body :deep(li) {
  margin: 0.15em 0;
}
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 0.6em 0 0.3em;
  font-weight: 600;
}
.md-body :deep(code) {
  background: #f4f4f5;
  border-radius: 4px;
  padding: 0.1em 0.35em;
  font-size: 0.9em;
}
.md-body :deep(pre) {
  background: #f4f4f5;
  border-radius: 8px;
  padding: 0.75em 1em;
  overflow-x: auto;
}
.md-body :deep(pre code) {
  background: none;
  padding: 0;
}
.md-body :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 0.3em 0.7em;
}
.md-body :deep(blockquote) {
  border-left: 3px solid #dcdfe6;
  padding-left: 0.8em;
  color: #909399;
  margin: 0.5em 0;
}

/* 行内引用上标 */
.md-body :deep(.cite-mark) {
  color: #409eff;
  font-weight: 600;
  margin: 0 1px;
}

/* 思考过程折叠面板弱化 */
.trace-collapse {
  border: none;
  max-width: 42rem;
}
.trace-collapse :deep(.el-collapse-item__header) {
  height: 28px;
  line-height: 28px;
  font-size: 12px;
  color: #909399;
  border-bottom: none;
  background: transparent;
}
.trace-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}
.trace-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}

/* “思考中”动画 */
.dotting::after {
  content: "…";
  animation: dotting 1.2s infinite steps(4, start);
}
@keyframes dotting {
  0% {
    content: "";
  }
  25% {
    content: ".";
  }
  50% {
    content: "..";
  }
  75% {
    content: "...";
  }
  100% {
    content: "";
  }
}
</style>
