<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "@/utils/http";

defineOptions({ name: "Search" });

interface SearchItem {
  chunkId: number;
  docId: number;
  docTitle: string;
  sectionPath: string;
  page: number | null;
  text: string;
  score: number;
}

interface DocRow {
  id: number;
  title: string;
  status: string;
}

const query = ref("");
const docIds = ref<number[]>([]);
const docs = ref<DocRow[]>([]);
const items = ref<SearchItem[]>([]);
const searching = ref(false);
const searched = ref(false);

async function loadDocs() {
  const res = await http.request<{
    code: number;
    data: { records: DocRow[] };
  }>("get", "/api/documents", { params: { page: 1, size: 100 } });
  if (res.code === 0) {
    docs.value = res.data.records.filter(d => d.status === "READY");
  }
}

async function doSearch() {
  const q = query.value.trim();
  if (!q) return;
  searching.value = true;
  searched.value = true;
  try {
    const res = await http.request<{
      code: number;
      message: string;
      data: { items: SearchItem[] };
    }>("post", "/api/search", {
      data: { query: q, docIds: docIds.value.length ? docIds.value : undefined, topK: 10 }
    });
    if (res.code === 0) {
      items.value = res.data?.items || [];
    } else {
      ElMessage.error(res.message || "检索失败");
    }
  } finally {
    searching.value = false;
  }
}

/** 转义后高亮查询词(先 HTML escape 再插 <mark>,防注入) */
function highlight(text: string): string {
  const esc = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const terms = [...new Set(query.value.trim().split(/\s+/).filter(t => t.length > 1))]; // eslint-disable-line
  let out = esc;
  for (const t of terms) {
    const safe = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(`(${safe})`, "gi"), "<mark>$1</mark>");
  }
  return out;
}

onMounted(loadDocs);
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex items-center gap-2">
        <span class="font-bold mr-2">智能检索</span>
        <el-select
          v-model="docIds"
          multiple
          collapse-tags
          clearable
          placeholder="全部文档"
          class="w-64"
        >
          <el-option
            v-for="d in docs"
            :key="d.id"
            :label="d.title"
            :value="d.id"
          />
        </el-select>
        <span class="text-xs text-gray-400">混合检索:语义 + 关键词</span>
      </div>
    </template>

    <div class="flex gap-2 mb-4">
      <el-input
        v-model="query"
        clearable
        placeholder="输入关键词或自然语言问题,Enter 检索"
        @keydown.enter="doSearch"
      />
      <el-button type="primary" :loading="searching" @click="doSearch">检索</el-button>
    </div>

    <el-empty v-if="searched && !items.length && !searching" description="无匹配结果(需先有 READY 文档,且未配置 API key 时无法生成向量)" />

    <div v-for="it in items" :key="it.chunkId" class="mb-3 border rounded p-3 hover:bg-gray-50">
      <div class="flex items-center justify-between mb-1">
        <div class="text-sm font-bold">
          {{ it.docTitle }}
          <span class="text-xs text-gray-400 font-normal">
            {{ it.sectionPath }}{{ it.page != null ? " · 第" + it.page + "页" : "" }}
          </span>
        </div>
        <el-tag size="small" type="info" effect="plain">{{ it.score }}</el-tag>
      </div>
      <div class="text-sm text-gray-600 leading-6" v-html="highlight(it.text)" />
    </div>
  </el-card>
</template>
