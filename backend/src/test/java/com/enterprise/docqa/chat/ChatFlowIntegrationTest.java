package com.enterprise.docqa.chat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * M2W4-1 验收:SSE 透传全链(meta/trace/token/citations/done)、
 * assistant 消息落库(citations/trace/latency)、断连不落库(§8.4)。
 * MockWebServer 假冒 Python /chat。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ChatFlowIntegrationTest {

    static MockWebServer python;

    @org.springframework.boot.test.web.server.LocalServerPort
    int portHolder;

    @Autowired
    ChatService chatService;

    @Autowired
    ChatSessionRepository sessionRepository;

    @Autowired
    ChatMessageRepository messageRepository;

    @Autowired
    ObjectMapper om;

    @BeforeAll
    static void start() throws IOException {
        python = new MockWebServer();
        python.start();
    }

    @AfterAll
    static void stop() throws IOException {
        python.shutdown();
    }

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("ai.base-url", () -> python.url("/").toString());
    }

    private static String sse(String event, String data) {
        return "event: " + event + "\ndata: " + data + "\n\n";
    }

    @Test
    void fullStream_persistsAssistantWithCitationsAndTrace() throws Exception {
        python.enqueue(new MockResponse().setBody(
                sse("trace", "{\"node\":\"retrieve\",\"status\":\"end\",\"detail\":\"hits=2\",\"tsMs\":12}")
                        + sse("token", "{\"text\":\"年假为5天\"}")
                        + sse("token", "{\"text\":\"，满10年为10天[1]\"}")
                        + sse("citations", "{\"items\":[{\"no\":1,\"chunkId\":9,\"docId\":5,\"docTitle\":\"员工手册\",\"sectionPath\":\"员工手册 > 假期\",\"page\":3,\"text\":\"年假...\"}]}")
                        + sse("done", "{\"latencyMs\":823}")
        ).setHeader("Content-Type", "text/event-stream"));

        var session = chatService.createSession(null, "年假问题");
        long sessionId = session.getId();

        HttpClient http = HttpClient.newHttpClient();
        HttpResponse<java.io.InputStream> resp = http.send(
                HttpRequest.newBuilder()
                        .uri(URI.create("http://localhost:" + portHolder + "/api/chat"))
                        .timeout(Duration.ofSeconds(30))
                        .header("Content-Type", "application/json")
                        .header("Authorization", "Bearer " + tokenOfAdmin())
                        .POST(HttpRequest.BodyPublishers.ofString(
                                "{\"sessionId\":" + sessionId + ",\"message\":\"年假有几天\"}"))
                        .build(),
                HttpResponse.BodyHandlers.ofInputStream());

        StringBuilder raw = new StringBuilder();
        try (var reader = new java.io.BufferedReader(
                new java.io.InputStreamReader(resp.body()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                raw.append(line).append('\n');
            }
        }
        String all = raw.toString();
        assertThat(all).contains("event:meta");
        assertThat(all).contains("event:trace");
        assertThat(all).contains("年假为5天");
        assertThat(all).contains("event:citations");
        assertThat(all).contains("event:done");
        assertThat(all).contains("assistantMessageId");

        // DB 断言:user + assistant 两行,assistant 带引用/trace/latency
        List<ChatMessage> msgs = messageRepository.findBySessionIdOrderByIdAsc(sessionId);
        assertThat(msgs).hasSize(2);
        ChatMessage assistant = msgs.get(1);
        assertThat(assistant.getRole()).isEqualTo("assistant");
        assertThat(assistant.getContent()).contains("年假为5天").contains("[1]");
        assertThat(assistant.getCitations()).contains("员工手册");
        assertThat(assistant.getTrace()).contains("retrieve");
        assertThat(assistant.getLatencyMs()).isEqualTo(823);

        cleanup(sessionId);
    }

    @Test
    void clientDisconnect_noAssistantRow() throws Exception {
        // 上游 done 延迟 3 秒到达;期间前端断开(emitter.complete 模拟 §8.4 取消)
        python.enqueue(new MockResponse()
                .setBody(sse("trace", "{\"node\":\"retrieve\",\"status\":\"end\",\"detail\":\"hits=1\",\"tsMs\":5}")
                        + sse("token", "{\"text\":\"部分\"}")
                        + sse("done", "{\"latencyMs\":50}"))
                .setHeadersDelay(3, TimeUnit.SECONDS)
                .setHeader("Content-Type", "text/event-stream"));

        var session = chatService.createSession(null, "断连测试");
        long sessionId = session.getId();
        long messageId = chatService.saveUserMessage(sessionId, "断连");

        // 直接走 gateway:注入依赖
        SseGateway gw = new SseGateway(messageRepository, chatService);
        setField(gw, "baseUrl", python.url("/").toString());
        setField(gw, "internalToken", "dev-doc-qa-internal-token");
        var emitter = gw.newEmitter();
        gw.stream(emitter, sessionId, messageId, "断连");
        emitter.complete(); // 模拟客户端断开,立即触发 onCompletion → 取消上游
        Thread.sleep(4000); // 等(被取消的)上游结束

        List<ChatMessage> msgs = messageRepository.findBySessionIdOrderByIdAsc(sessionId);
        assertThat(msgs).hasSize(1); // 只有 user,无 assistant 半截消息
        assertThat(msgs.get(0).getRole()).isEqualTo("user");
        assertThat(chatService.hasAssistantMessage(sessionId, messageId)).isFalse();

        cleanup(sessionId);
    }

    private String tokenOfAdmin() throws Exception {
        HttpResponse<String> login = HttpClient.newHttpClient().send(
                HttpRequest.newBuilder()
                        .uri(URI.create("http://localhost:" + portHolder + "/api/auth/login"))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(
                                "{\"username\":\"admin\",\"password\":\"admin123\"}"))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        JsonNode node = om.readTree(login.body());
        return node.at("/data/token").asText();
    }

    private void cleanup(long sessionId) {
        messageRepository.deleteAll(messageRepository.findBySessionIdOrderByIdAsc(sessionId));
        sessionRepository.deleteById(sessionId);
    }

    private static void setField(Object target, String name, Object value) throws Exception {
        var f = target.getClass().getDeclaredField(name);
        f.setAccessible(true);
        f.set(target, value);
    }
}
