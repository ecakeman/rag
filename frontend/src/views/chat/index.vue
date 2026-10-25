<script setup lang="ts">
defineOptions({ name: "Chat" });
</script>

<template>
  <el-card shadow="never">
    <template #header><span class="font-bold">AI 知识问答</span></template>
    <el-empty description="问答链路建设中(M2W4 接入 SSE 流式对话)" />
  </el-card>
</template>
