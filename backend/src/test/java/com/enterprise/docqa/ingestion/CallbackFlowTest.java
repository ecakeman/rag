package com.enterprise.docqa.ingestion;

import com.enterprise.docqa.document.DocStatus;
import com.enterprise.docqa.document.DocumentEntity;
import com.enterprise.docqa.document.DocumentRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** M1W2-1 验收:回调状态迁移(PROCESSING/READY/FAILED)+ internal token 防护 */
@SpringBootTest
@AutoConfigureMockMvc
class CallbackFlowTest {

    private static final String TOKEN = "dev-doc-qa-internal-token";

    @Autowired
    MockMvc mvc;

    @Autowired
    DocumentRepository repo;

    private DocumentEntity newDoc(DocStatus st) {
        DocumentEntity d = new DocumentEntity();
        d.setTitle("t");
        d.setFileName("a.pdf");
        d.setFilePath("data/files/x.pdf");
        d.setFileSize(1);
        d.setStatus(st);
        return repo.save(d);
    }

    @Test
    void callback_processing_then_ready() throws Exception {
        DocumentEntity doc = newDoc(DocStatus.NOTIFIED);
        mvc.perform(post("/api/internal/ingest/callback")
                        .header("X-Internal-Token", TOKEN)
                        .contentType("application/json")
                        .content("{\"docId\":%d,\"status\":\"PROCESSING\"}".formatted(doc.getId())))
                .andExpect(status().isNoContent());
        assertThat(repo.findById(doc.getId()).orElseThrow().getStatus()).isEqualTo(DocStatus.PROCESSING);

        mvc.perform(post("/api/internal/ingest/callback")
                        .header("X-Internal-Token", TOKEN)
                        .contentType("application/json")
                        .content("{\"docId\":%d,\"status\":\"READY\",\"chunkCount\":23}".formatted(doc.getId())))
                .andExpect(status().isNoContent());
        DocumentEntity after = repo.findById(doc.getId()).orElseThrow();
        assertThat(after.getStatus()).isEqualTo(DocStatus.READY);
        assertThat(after.getChunkCount()).isEqualTo(23);

        repo.delete(after);
    }

    @Test
    void callback_failed_setsErrorMsg() throws Exception {
        DocumentEntity doc = newDoc(DocStatus.PROCESSING);
        mvc.perform(post("/api/internal/ingest/callback")
                        .header("X-Internal-Token", TOKEN)
                        .contentType("application/json")
                        .content("{\"docId\":%d,\"status\":\"FAILED\",\"errorMsg\":\"boom\"}".formatted(doc.getId())))
                .andExpect(status().isNoContent());
        DocumentEntity after = repo.findById(doc.getId()).orElseThrow();
        assertThat(after.getStatus()).isEqualTo(DocStatus.FAILED);
        assertThat(after.getErrorMsg()).isEqualTo("boom");
        repo.delete(after);
    }

    @Test
    void callback_wrongToken_401() throws Exception {
        mvc.perform(post("/api/internal/ingest/callback")
                        .header("X-Internal-Token", "bad")
                        .contentType("application/json")
                        .content("{\"docId\":1,\"status\":\"READY\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void callback_unknownStatus_422() throws Exception {
        DocumentEntity doc = newDoc(DocStatus.NOTIFIED);
        mvc.perform(post("/api/internal/ingest/callback")
                        .header("X-Internal-Token", TOKEN)
                        .contentType("application/json")
                        .content("{\"docId\":%d,\"status\":\"WEIRD\"}".formatted(doc.getId())))
                .andExpect(status().isUnprocessableEntity());
        repo.delete(doc);
    }
}
