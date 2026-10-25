package com.enterprise.docqa.ingestion;

import com.enterprise.docqa.document.DocStatus;
import com.enterprise.docqa.document.DocumentEntity;
import com.enterprise.docqa.document.DocumentRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 对账 Job(§4.4):
 * - NOTIFIED 超 5 分钟未变 → 重发 /ingest(Python 按 docId 幂等)
 * - PROCESSING 超 10 分钟未变 → 主动查状态;仍无果 → FAILED(处理超时)
 */
@Slf4j
@Component
public class ReconcileJob {

    private final DocumentRepository repo;
    private final IngestClient ingestClient;

    @Value("${ai.callback-url}")
    private String callbackUrl;

    public ReconcileJob(DocumentRepository repo, IngestClient ingestClient) {
        this.repo = repo;
        this.ingestClient = ingestClient;
    }

    @Scheduled(fixedDelay = 60_000, initialDelay = 90_000)
    public void reconcile() {
        OffsetDateTime now = OffsetDateTime.now();

        List<DocumentEntity> staleNotified =
                repo.findByStatusAndUpdatedAtBefore(DocStatus.NOTIFIED, now.minusMinutes(5));
        for (DocumentEntity doc : staleNotified) {
            try {
                ingestClient.notifyIngest(doc.getId(), doc.getFilePath(), doc.getFileName(),
                        doc.getTitle(), callbackUrl);
                doc.setUpdatedAt(OffsetDateTime.now()); // 重发后重新计时
                repo.save(doc);
                log.warn("[reconcile] doc {} NOTIFIED 超时,已重发 ingest", doc.getId());
            } catch (Exception e) {
                log.error("[reconcile] doc {} 重发失败: {}", doc.getId(), e.getMessage());
            }
        }

        List<DocumentEntity> staleProcessing =
                repo.findByStatusAndUpdatedAtBefore(DocStatus.PROCESSING, now.minusMinutes(10));
        for (DocumentEntity doc : staleProcessing) {
            try {
                IngestClient.IngestStatus st = ingestClient.status(doc.getId());
                if ("READY".equals(st.status())) {
                    doc.setStatus(DocStatus.READY);
                    doc.setErrorMsg(null);
                    if (st.chunkCount() != null) {
                        doc.setChunkCount(st.chunkCount());
                    }
                    repo.save(doc);
                    log.warn("[reconcile] doc {} 对账为 READY", doc.getId());
                } else if ("FAILED".equals(st.status())) {
                    doc.setStatus(DocStatus.FAILED);
                    doc.setErrorMsg(st.errorMsg() == null ? "AI 服务处理失败(对账)" : st.errorMsg());
                    repo.save(doc);
                } else {
                    // 仍 PROCESSING:touch 更新时间,下一轮再查
                    doc.setUpdatedAt(OffsetDateTime.now());
                    repo.save(doc);
                }
            } catch (Exception e) {
                doc.setStatus(DocStatus.FAILED);
                doc.setErrorMsg("处理超时: " + e.getMessage());
                repo.save(doc);
                log.error("[reconcile] doc {} 判定失败: {}", doc.getId(), e.getMessage());
            }
        }
    }
}
