<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "@/utils/http";

defineOptions({ name: "Settings" });

interface ConfigItem {
  key: string;
  label: string;
  group: string;
  secret: boolean;
  source: "db" | "env";
  value: string;
}

const loading = ref(false);
const saving = ref(false);
const items = ref<ConfigItem[]>([]);
const form = ref<Record<string, string>>({});

const groups = computed(() => {
  const map = new Map<string, ConfigItem[]>();
  for (const it of items.value) {
    if (!map.has(it.group)) map.set(it.group, []);
    map.get(it.group)!.push(it);
  }
  return Array.from(map.entries());
});

async function load() {
  loading.value = true;
  try {
    const res = await http.request<{ code: number; data: ConfigItem[] }>(
      "get",
      "/api/admin/config"
    );
    if (res.code === 0) {
      items.value = res.data;
      form.value = {};
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || "加载配置失败");
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const res = await http.request<{ code: number; message: string }>(
      "put",
      "/api/admin/config",
      { data: form.value }
    );
    if (res.code === 0) {
      ElMessage.success("已保存，约 15 秒内生效（无需重启服务）");
      await load();
    } else {
      ElMessage.error(res.message || "保存失败");
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || "保存失败");
  } finally {
    saving.value = false;
  }
}

function placeholder(it: ConfigItem): string {
  if (it.value) {
    const src = it.source === "db" ? "已配置" : "环境变量默认";
    return `${src}：${it.value}（留空保持不变）`;
  }
  return it.secret ? "未配置（留空保持不变）" : "未配置";
}

/** 空值提交 = 清除覆盖、回落环境变量默认 */
async function resetOverride(it: ConfigItem) {
  try {
    const res = await http.request<{ code: number; message: string }>(
      "put",
      "/api/admin/config",
      { data: { [it.key]: "" } }
    );
    if (res.code === 0) {
      ElMessage.success(`已恢复「${it.label}」为环境变量默认`);
      await load();
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || "操作失败");
  }
}

onMounted(load);
</script>

<template>
  <div class="max-w-3xl mx-auto py-4 space-y-4" v-loading="loading">
    <el-card v-for="[group, list] in groups" :key="group" shadow="never">
      <template #header>
        <span class="font-semibold">{{ group }}</span>
      </template>
      <el-form label-width="190px" label-position="left">
        <el-form-item v-for="it in list" :key="it.key" :label="it.label">
          <div class="flex w-full items-center gap-2">
            <el-input
              v-if="it.secret"
              v-model="form[it.key]"
              type="password"
              show-password
              autocomplete="new-password"
              :placeholder="placeholder(it)"
              clearable
            />
            <el-input
              v-else
              v-model="form[it.key]"
              :placeholder="placeholder(it)"
              clearable
            />
            <el-button
              v-if="it.source === 'db'"
              plain
              size="small"
              @click="resetOverride(it)"
            >
              恢复默认
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="flex justify-end">
      <el-button type="primary" :loading="saving" @click="save">
        保存配置
      </el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="说明"
      description="此处配置优先于部署环境变量，保存后 AI 服务约 15 秒内自动生效；将某项清空保存即恢复为环境变量默认值。向量维度在建库时固定，不支持在此修改。"
    />
  </div>
</template>
