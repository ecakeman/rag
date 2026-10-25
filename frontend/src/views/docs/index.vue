<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadRequestOptions } from "element-plus";
import { http } from "@/utils/http";

defineOptions({ name: "Docs" });

interface DocRow {
  id: number;
  title: string;
  fileName: string;
  fileSize: number;
  status: string;
  errorMsg: string | null;
  chunkCount: number;
  createdAt: string;
}

const loading = ref(false);
const rows = ref<DocRow[]>([]);
const total = ref(0);
const page = ref(1);
const size = ref(10);
const pollTimer = ref<number>();

const ALLOWED = ["pdf", "docx", "md", "txt"];

async function load() {
  loading.value = true;
  try {
    const res = await http.request<{
      code: number;
      data: { total: number; records: DocRow[] };
    }>("get", "/api/documents", {
      params: { page: page.value, size: size.value }
    });
    if (res.code === 0) {
      rows.value = res.data.records;
      total.value = res.data.total;
    }
  } finally {
    loading.value = false;
  }
  schedulePoll();
}

/** 仅对未到终态的行 3s 轮询(DESIGN §9.2) */
function schedulePoll() {
  if (pollTimer.value) window.clearInterval(pollTimer.value);
  pollTimer.value = window.setInterval(async () => {
    const active = rows.value.filter(r =>
      ["UPLOADED", "NOTIFIED", "PROCESSING"].includes(r.status)
    );
    if (!active.length) return;
    const res = await http.request<{
      code: number;
      data: { records: DocRow[] };
    }>("get", "/api/documents", {
      params: { page: page.value, size: size.value }
    });
    if (res.code === 0) {
      rows.value = rows.value.map(old => {
        const fresh = res.data.records.find(r => r.id === old.id);
        return fresh ? { ...old, ...fresh } : old;
      });
    }
  }, 3000);
}

function beforeUpload(file: File) {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED.includes(ext)) {
    ElMessage.error(`仅支持 ${ALLOWED.join("/")} 格式`);
    return false;
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error("文件不能超过 50MB");
    return false;
  }
  return true;
}

async function doUpload(option: UploadRequestOptions) {
  const form = new FormData();
  form.append("file", option.file);
  try {
    const res = await http.request<{ code: number; message: string }>(
      "post",
      "/api/documents",
      { data: form }
    );
    if (res.code === 0) {
      ElMessage.success("已上传,等待解析");
      page.value = 1;
      await load();
    } else {
      ElMessage.error(res.message || "上传失败");
    }
  } catch (e) {
    ElMessage.error("上传失败");
  }
}

async function onDelete(row: DocRow) {
  await ElMessageBox.confirm(`确认删除「${row.title}」?将同时清理其知识块`, "删除确认", {
    type: "warning"
  });
  const res = await http.request<{ code: number; message: string }>(
    "delete",
    `/api/documents/${row.id}`
  );
  if (res.code === 0) {
    ElMessage.success("已删除");
    await load();
  } else {
    ElMessage.error(res.message || "删除失败");
  }
}

function fmtSize(n: number) {
  return n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : (n / 1024).toFixed(1) + " KB";
}

onMounted(load);
onBeforeUnmount(() => pollTimer.value && window.clearInterval(pollTimer.value));
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-bold">企业文档库</span>
        <el-upload
          :show-file-list="false"
          :http-request="doUpload"
          :before-upload="beforeUpload"
          accept=".pdf,.docx,.md,.txt"
        >
          <el-button type="primary">上传文档</el-button>
        </el-upload>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="fileName" label="文件名" min-width="140" show-overflow-tooltip />
      <el-table-column label="大小" width="90">
        <template #default="{ row }">{{ fmtSize(row.fileSize) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'READY'" type="success">READY</el-tag>
          <el-tooltip v-else-if="row.status === 'FAILED'" :content="row.errorMsg || '处理失败'" placement="top">
            <el-tag type="danger">FAILED</el-tag>
          </el-tooltip>
          <el-tag v-else type="info" effect="plain">{{ row.status }}…</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="chunkCount" label="知识块" width="80" />
      <el-table-column prop="createdAt" label="上传时间" width="170">
        <template #default="{ row }">
          {{ new Date(row.createdAt).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="size"
      :total="total"
      layout="total, prev, pager, next"
      class="mt-4"
      @current-change="load"
    />
  </el-card>
</template>
