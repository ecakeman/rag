<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { http } from "@/utils/http";
import { getToken } from "@/utils/auth";

defineOptions({ name: "Chat" });

interface Citation {
  no: number;
  chunkId: number;
  docTitle: string;
  sectionPath: string;
  page: number | null;
  text: string;
}

interface Bubble {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  trace: { node: string; detail?: string }[];
  latencyMs?: number;
}

interface Session {
  sessionId: number;
  title: string;
}

const sessions = ref<Session[]>([]);
const currentSession = ref<number | null>(null);
const bubbles = ref<Bubble[]>([]);
const input = ref("");
const sending = ref(false);
const traceVisible = ref(true);
const drawerCitations = ref<Citation[] | null>(null);
const listEl = ref<HTMLElement>();
let ctrl: AbortController | null = null;

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
      trace: { node: string; detail?: string }[] | null;
    }[];
  }>("get", `/api/chat/sessions/${id}/messages`);
  if (res.code === 0) {
    bubbles.value = res.data.map(m => ({
      role: m.role as "user" | "assistant",
      content: m.content,
      citations: m.citations || [],
      trace: m.trace || []
    }));
  }
}

async function deleteSession(id: number) {
  await ElMessageBox.confirm("删除该会话及其全部消息?", "删除会话", { type: "warning" });
  try {
    const res = await http.request<{ code: number; message: string }>(
      "delete", `/api/chat/sessions/${id}`);
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
  const assistant: Bubble = { role: "assistant", content: "", citations: [], trace: [] };
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
          assistant.latencyMs = data.latencyMs;
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
  <div class="flex gap-2 w-full" style="height: calc(100vh - 132px)">
    <!-- 会话列表 -->
    <el-card shadow="never" class="w-52 shrink-0" body-style="padding:8px;overflow-y:auto">
      <el-button type="primary" class="w-full mb-2" @click="newSession">
        新建会话
      </el-button>
      <div
        v-for="s in sessions"
        :key="s.sessionId"
        class="cursor-pointer rounded px-2 py-1.5 text-sm truncate hover:bg-gray-50 flex items-center justify-between group"
        :class="{ 'bg-sky-100': currentSession === s.sessionId }"
        @click="openSession(s.sessionId)"
      >
        <span class="truncate">{{ s.title }}</span>
        <span
          class="shrink-0 ml-1 hidden group-hover:inline-block text-xs text-gray-400 hover:text-red-500"
          @click.stop="deleteSession(s.sessionId)"
        >
          删除
        </span>
      </div>
    </el-card>

    <!-- 主对话区 -->
    <el-card shadow="never" class="flex-1 flex flex-col overflow-hidden" body-style="padding:0;flex:1;display:flex;overflow:hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-bold">AI 知识问答</span>
          <el-switch v-model="traceVisible" active-text="思考过程" size="small" />
        </div>
      </template>

      <div ref="listEl" class="flex-1 overflow-y-auto p-4 space-y-3">
        <el-empty v-if="!bubbles.length" description="新建会话后提问,回答将带引用出处" />
        <div v-for="(b, i) in bubbles" :key="i" class="flex" :class="b.role === 'user' ? 'justify-end' : 'justify-start'">
          <div
            class="max-w-[78%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap leading-6"
            :class="b.role === 'user' ? 'bg-sky-500 text-white' : 'bg-gray-100'"
          >
            <div>
              <template v-for="(seg, j) in b.content.split(/(\[\d{1,2}\])/g)" :key="j">
                <el-link
                  v-if="/^\[\d{1,2}\]$/.test(seg)"
                  type="primary"
                  :underline="false"
                  @click="drawerCitations = b.citations"
                >
                  {{ seg }}
                </el-link>
                <template v-else>{{ seg }}</template>
              </template>
              <span v-if="b.role === 'assistant' && !b.content && sending" class="text-gray-400">
                思考中…
              </span>
            </div>

            <!-- 思考过程 -->
            <el-collapse v-if="traceVisible && b.trace.length" class="mt-1 border-none">
              <el-collapse-item title="思考过程" name="t">
                <div v-for="(t, k) in b.trace" :key="k" class="text-xs text-gray-500">
                  <el-tag size="small" effect="plain" class="mr-1">{{ t.node }}</el-tag>
                  <span>{{ t.detail }}</span>
                </div>
              </el-collapse-item>
            </el-collapse>

            <div v-if="b.citations.length" class="mt-1 text-xs opacity-80">
              <el-tag
                v-for="c in b.citations"
                :key="c.no"
                size="small"
                class="mr-1 cursor-pointer"
                @click="drawerCitations = b.citations"
              >
                [{{ c.no }}] {{ c.docTitle }}
              </el-tag>
              <span v-if="b.latencyMs" class="ml-1">{{ (b.latencyMs / 1000).toFixed(1) }}s</span>
            </div>
          </div>
        </div>
      </div>

      <div class="border-t p-3 flex gap-2">
        <el-input
          v-model="input"
          :disabled="sending"
          placeholder="输入问题,Enter 发送 / Shift+Enter 换行"
          @keydown.enter.exact.prevent="send"
        />
        <el-button v-if="!sending" type="primary" @click="send">发送</el-button>
        <el-button v-else type="danger" @click="stop">停止</el-button>
      </div>
    </el-card>

    <!-- 引用抽屉 -->
    <el-drawer v-model="drawerCitations" :with-header="false" size="36%">
      <div v-for="c in drawerCitations || []" :key="c.no" class="mb-4">
        <div class="text-sm font-bold mb-1">
          [{{ c.no }}] {{ c.docTitle }}
          <span class="text-xs text-gray-400 font-normal">
            {{ c.sectionPath }}{{ c.page != null ? " · 第" + c.page + "页" : "" }}
          </span>
        </div>
        <div class="text-sm text-gray-600 bg-gray-50 rounded p-2 leading-6">{{ c.text }}</div>
      </div>
    </el-drawer>
  </div>
</template>
