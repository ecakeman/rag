package com.enterprise.docqa.config;

import com.enterprise.docqa.common.R;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 系统设置页后端(DESIGN §13 系统管理)：
 * LLM/Embedding/Rerank 连接信息由管理员在页面维护，写入 system_config 表，
 * Python 服务以 15s TTL 读取覆盖环境变量，免重启生效。
 */
@RestController
@RequestMapping("/api/admin/config")
public class ConfigController {

    /** 配置项定义：存储 key、环境变量默认值、是否脱敏、展示名、分组 */
    private record Def(String key, String env, boolean secret, String label, String group) {
    }

    private static final List<Def> DEFS = List.of(
            new Def("llm.base_url", "LLM_BASE_URL", false, "API Base URL", "模型服务 (LLM)"),
            new Def("llm.api_key", "LLM_API_KEY", true, "API Key", "模型服务 (LLM)"),
            new Def("llm.fast_model", "LLM_FAST_MODEL", false, "快速模型（路由/评估）", "模型服务 (LLM)"),
            new Def("llm.synth_model", "LLM_SYNTH_MODEL", false, "生成模型（回答合成）", "模型服务 (LLM)"),
            new Def("embed.base_url", "EMBED_BASE_URL", false, "API Base URL（空则沿用 LLM）", "向量服务 (Embedding)"),
            new Def("embed.api_key", "EMBED_API_KEY", true, "API Key（空则沿用 LLM）", "向量服务 (Embedding)"),
            new Def("embed.model", "EMBED_MODEL", false, "模型名", "向量服务 (Embedding)"),
            new Def("rerank.base_url", "RERANK_BASE_URL", false, "API Base URL", "重排服务 (Rerank)"),
            new Def("rerank.api_key", "RERANK_API_KEY", true, "API Key", "重排服务 (Rerank)"),
            new Def("rerank.model", "RERANK_MODEL", false, "模型名", "重排服务 (Rerank)")
    );

    private final SystemConfigRepository repo;

    public ConfigController(SystemConfigRepository repo) {
        this.repo = repo;
    }

    /** 当前生效配置视图：DB 覆盖优先，缺失回落环境变量；密钥脱敏展示。 */
    @GetMapping
    public R<List<Map<String, Object>>> get() {
        Map<String, String> db = new LinkedHashMap<>();
        repo.findAll().forEach(e -> db.put(e.getKey(), e.getValue()));
        List<Map<String, Object>> items = new ArrayList<>();
        for (Def def : DEFS) {
            String override = db.get(def.key());
            String envDefault = System.getenv().getOrDefault(def.env(), "");
            String effective = override != null ? override : envDefault;
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("key", def.key());
            item.put("label", def.label());
            item.put("group", def.group());
            item.put("secret", def.secret());
            item.put("source", override != null ? "db" : "env");
            item.put("value", def.secret() ? mask(effective) : effective);
            items.add(item);
        }
        return R.ok(items);
    }

    /** 保存覆盖：非空值 upsert；空值删除覆盖（回落环境变量默认）。 */
    @PutMapping
    @Transactional
    public R<Void> save(@RequestBody Map<String, String> configs) {
        Instant now = Instant.now();
        for (Def def : DEFS) {
            String value = configs.get(def.key());
            if (value == null) {
                continue; // 未提交的字段保持不变
            }
            String trimmed = value.trim();
            if (trimmed.isEmpty()) {
                repo.deleteById(def.key());
            } else {
                SystemConfigEntity entity = repo.findById(def.key()).orElseGet(SystemConfigEntity::new);
                entity.setKey(def.key());
                entity.setValue(trimmed);
                entity.setUpdatedAt(now);
                repo.save(entity);
            }
        }
        return R.ok();
    }

    private static String mask(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        if (value.length() <= 8) {
            return "****";
        }
        return value.substring(0, 4) + "****" + value.substring(value.length() - 4);
    }
}
