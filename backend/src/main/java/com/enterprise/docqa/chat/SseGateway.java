package com.enterprise.docqa.chat;

import com.enterprise.docqa.common.BizException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * SSE 透传网关(DESIGN §6.4):JDK HttpClient 流式读 Python /chat,SseEmitter 写回前端。
 * 断连语义(§8.4):emitter 结束(完成/超时/错误)→ 取消上游读取,半截 assistant 消息不落库。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class SseGateway {

    private final ChatMessageRepository messageRepository;
    private final ChatService chatService;

    @Value("${ai.base-url}")
    private String baseUrl;

    @Value("${ai.internal-token}")
    private String internalToken;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)  // uvicorn 不支持 h2c 升级
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    public SseEmitter newEmitter() {
        return new SseEmitter(120_000L);
    }

    public void stream(SseEmitter emitter, long sessionId, long messageId, String message) {
        AtomicBoolean upstreamCancelled = new AtomicBoolean(false);
        java.util.concurrent.atomic.AtomicReference<java.io.InputStream> bodyRef =
                new java.util.concurrent.atomic.AtomicReference<>();

        StringBuilder content = new StringBuilder();
        List<String> traceEvents = new ArrayList<>();
        String[] citations = {null};
        Integer[] latency = {null};

        CompletableFuture<Void> upstream = CompletableFuture.runAsync(() -> {
            try {
                String body = chatService.buildPythonChatBody(sessionId, messageId, message);
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(baseUrl + "/chat"))
                        .timeout(Duration.ofSeconds(180))
                        .header("Content-Type", "application/json")
                        .header("Accept", "text/event-stream")
                        .header("X-Internal-Token", internalToken)
                        .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                        .build();

                HttpResponse<java.io.InputStream> resp = httpClient.send(
                        request, HttpResponse.BodyHandlers.ofInputStream());
                bodyRef.set(resp.body());
                if (resp.statusCode() != 200) {
                    emitter.send(SseEmitter.event().name("error")
                            .data("{\"code\":5032,\"message\":\"AI 服务返回 " + resp.statusCode() + "\"}"));
                    emitter.complete();
                    return;
                }

                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(resp.body(), StandardCharsets.UTF_8))) {
                    String line;
                    String currentEvent = null;
                    while (!upstreamCancelled.get() && (line = reader.readLine()) != null) {
                        if (line.startsWith("event: ")) {
                            currentEvent = line.substring(7).trim();
                        } else if (line.startsWith("data: ")) {
                            String data = line.substring(6);
                            forward(emitter, currentEvent, data);
                            if ("token".equals(currentEvent)) {
                                content.append(extractTextField(data));
                            } else if ("trace".equals(currentEvent)) {
                                traceEvents.add(data);
                            } else if ("citations".equals(currentEvent)) {
                                citations[0] = data.contains("\"items\"")
                                        ? extractItemsArray(data) : null;
                            } else if ("done".equals(currentEvent)) {
                                latency[0] = extractLatency(data);
                                Long assistantId = chatService.saveAssistantMessage(
                                        sessionId, content.toString(), citations[0],
                                        traceEvents, latency[0]);
                                forward(emitter, "done",
                                        data.replaceAll("\"latencyMs\"", "\"assistantMessageId\":"
                                                + assistantId + ",\"latencyMs\""));
                                emitter.complete();
                                return;
                            } else if ("error".equals(currentEvent)) {
                                emitter.send(SseEmitter.event().name("error").data(data));
                                emitter.complete();
                                return;
                            }
                            currentEvent = null;
                        }
                    }
                    // 流意外中断(无 done/error)
                    if (!upstreamCancelled.get()) {
                        emitter.send(SseEmitter.event().name("error")
                                .data("{\"code\":5032,\"message\":\"AI 流意外中断\"}"));
                    }
                    emitter.complete();
                }
            } catch (Exception e) {
                if (!upstreamCancelled.get()) {
                    try {
                        emitter.send(SseEmitter.event().name("error")
                                .data("{\"code\":5031,\"message\":\"AI 服务不可达: "
                                        + e.getClass().getSimpleName() + "\"}"));
                    } catch (Exception ignored) {
                    }
                    emitter.complete();
                }
            }
        });

        // 客户端断开/超时 → 温和取消(不 interrupt,避免打断响应刷写;关闭上游流解除读阻塞)
        Runnable cancel = () -> {
            if (upstreamCancelled.compareAndSet(false, true)) {
                try {
                    java.io.InputStream body = bodyRef.get();
                    if (body != null) {
                        body.close();
                    }
                } catch (Exception ignored) {
                }
                upstream.cancel(false);
            }
        };
        emitter.onCompletion(cancel);
        emitter.onTimeout(() -> {
            cancel.run();
            emitter.complete();
        });
        emitter.onError(e -> cancel.run());
    }

    private void forward(SseEmitter emitter, String event, String data) throws Exception {
        if (event == null) {
            return;
        }
        emitter.send(SseEmitter.event().name(event).data(data, org.springframework.http.MediaType.APPLICATION_JSON));
    }

    private String extractTextField(String json) {
        // {"text":"..."} → 追加内容;仅做轻量提取,避免全文解析
        int i = json.indexOf("\"text\":\"");
        if (i < 0) {
            return "";
        }
        int start = i + 8;
        StringBuilder sb = new StringBuilder();
        for (int j = start; j < json.length(); j++) {
            char c = json.charAt(j);
            if (c == '\\' && j + 1 < json.length()) {
                char n = json.charAt(++j);
                sb.append(switch (n) {
                    case 'n' -> '\n';
                    case 't' -> '\t';
                    case 'r' -> '\r';
                    case '"' -> '"';
                    case '\\' -> '\\';
                    case '/' -> '/';
                    case 'u' -> ' '; // 罕见;token 流中按空格近似
                    default -> n;
                });
            } else if (c == '"' ) {
                break;
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private String extractItemsArray(String json) {
        int i = json.indexOf("\"items\":");
        if (i < 0) {
            return null;
        }
        int start = json.indexOf('[', i);
        int end = json.lastIndexOf(']');
        return (start >= 0 && end > start) ? json.substring(start, end + 1) : null;
    }

    private Integer extractLatency(String json) {
        try {
            int i = json.indexOf("\"latencyMs\":");
            if (i < 0) {
                return null;
            }
            int end = json.indexOf(',', i);
            return Integer.parseInt(json.substring(i + 12, end < 0 ? json.length() - 1 : end)
                    .replaceAll("[^0-9]", ""));
        } catch (Exception e) {
            return null;
        }
    }
}
