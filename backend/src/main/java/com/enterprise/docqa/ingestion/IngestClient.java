package com.enterprise.docqa.ingestion;

import com.enterprise.docqa.common.BizException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.util.Map;

/**
 * Java→Python 的 HTTP 客户端(§6.2):ingest 带 docId 幂等,可安全重试。
 * 超时/IO 错误重试 2 次(共 3 次尝试);4xx 不重试。
 */
@Slf4j
@Component
public class IngestClient {

    private final RestClient client;
    private final String baseUrl;
    private final String internalToken;
    private final int maxAttempts;

    public IngestClient(@Value("${ai.base-url}") String baseUrl,
                        @Value("${ai.internal-token}") String internalToken,
                        @Value("${ai.ingest-timeout}") Duration timeout) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) timeout.toMillis());
        factory.setReadTimeout((int) timeout.toMillis());
        this.client = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .defaultHeader("X-Internal-Token", internalToken)
                .build();
        this.baseUrl = baseUrl;
        this.internalToken = internalToken;
        this.maxAttempts = 3;
    }

    public void notifyIngest(long docId, String filePath, String fileName, String title, String callbackUrl) {
        Map<String, Object> body = Map.of(
                "docId", docId,
                "filePath", filePath,
                "fileName", fileName,
                "title", title,
                "callbackUrl", callbackUrl);
        withRetry("POST /ingest " + docId, () -> client.post().uri("/ingest")
                .body(body)
                .retrieve().toBodilessEntity());
    }

    public IngestStatus status(long docId) {
        return withRetry("GET /ingest/" + docId + "/status", () -> client.get()
                .uri("/ingest/{id}/status", docId)
                .retrieve().body(IngestStatus.class));
    }

    public void deleteChunks(long docId) {
        withRetry("DELETE /ingest/" + docId, () -> client.delete()
                .uri("/ingest/{id}", docId)
                .retrieve().toBodilessEntity());
    }

    private <T> T withRetry(String what, RestClientCallable<T> call) {
        RestClientException last = null;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                return call.get();
            } catch (org.springframework.web.client.RestClientResponseException e) {
                if (e.getStatusCode().is4xxClientError()) {
                    // 4xx 是确定性错误,重试无意义
                    throw new BizException(5032, "AI 服务拒绝请求(" + what + "): " + e.getStatusCode());
                }
                last = e;
                log.warn("[ingest] {} 第{}次失败: {}", what, attempt, e.getMessage());
            } catch (RestClientException e) {
                last = e;
                log.warn("[ingest] {} 第{}次失败: {}", what, attempt, e.getMessage());
            }
        }
        throw new BizException(5031, "AI 服务不可达(" + what + "): " + last.getMessage());
    }

    @FunctionalInterface
    private interface RestClientCallable<T> {
        T get() throws RestClientException;
    }

    public record IngestStatus(long docId, String status, Integer chunkCount, String errorMsg) {
    }
}
