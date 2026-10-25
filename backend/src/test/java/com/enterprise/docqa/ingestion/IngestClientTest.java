package com.enterprise.docqa.ingestion;

import com.enterprise.docqa.common.BizException;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClientException;

import java.io.IOException;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** M1W2-1 验收:ingest 202 / 超时重试2次 / 最终失败→BizException(5031) */
class IngestClientTest {

    MockWebServer server;

    @BeforeEach
    void start() throws IOException {
        server = new MockWebServer();
        server.start();
    }

    @AfterEach
    void stop() throws IOException {
        server.shutdown();
    }

    private IngestClient client() {
        return new IngestClient(server.url("/").toString(), "tok", Duration.ofMillis(2000));
    }

    @Test
    void notify_ok_202_singleAttempt() throws Exception {
        server.enqueue(new MockResponse().setResponseCode(202).setBody("{\"status\":\"QUEUED\"}"));
        client().notifyIngest(1, "data/files/1.pdf", "1.pdf", "t", "http://cb");
        assertThat(server.getRequestCount()).isEqualTo(1);
        var recorded = server.takeRequest();
        assertThat(recorded.getHeader("X-Internal-Token")).isEqualTo("tok");
        assertThat(recorded.getPath()).isEqualTo("/ingest");
    }

    @Test
    void notify_retryOn5xx_thenSuccess() {
        server.enqueue(new MockResponse().setResponseCode(502));
        server.enqueue(new MockResponse().setResponseCode(202).setBody("{\"status\":\"QUEUED\"}"));
        client().notifyIngest(1, "p", "f", "t", "http://cb");
        assertThat(server.getRequestCount()).isEqualTo(2);
    }

    @Test
    void notify_allFail_throws5031() {
        server.enqueue(new MockResponse().setResponseCode(500));
        server.enqueue(new MockResponse().setResponseCode(500));
        server.enqueue(new MockResponse().setResponseCode(500));
        assertThatThrownBy(() -> client().notifyIngest(1, "p", "f", "t", "http://cb"))
                .isInstanceOf(BizException.class)
                .satisfies(e -> assertThat(((BizException) e).getCode()).isEqualTo(5031));
        assertThat(server.getRequestCount()).isEqualTo(3);
    }

    @Test
    void status_parsesBody() {
        server.enqueue(new MockResponse().setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody("{\"docId\":7,\"status\":\"READY\",\"chunkCount\":42,\"errorMsg\":null}"));
        IngestClient.IngestStatus st = client().status(7);
        assertThat(st.status()).isEqualTo("READY");
        assertThat(st.chunkCount()).isEqualTo(42);
    }

    @Test
    void noRetry_on4xx() {
        server.enqueue(new MockResponse().setResponseCode(404));
        assertThatThrownBy(() -> client().status(9))
                .isInstanceOf(BizException.class);
        assertThat(server.getRequestCount()).isEqualTo(1);
    }

    @Test
    void delete_ok() {
        server.enqueue(new MockResponse().setResponseCode(204));
        client().deleteChunks(3);
        assertThat(server.getRequestCount()).isEqualTo(1);
    }
}
