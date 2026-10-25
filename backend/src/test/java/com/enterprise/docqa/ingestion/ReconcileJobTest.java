package com.enterprise.docqa.ingestion;

import com.enterprise.docqa.common.BizException;
import com.enterprise.docqa.document.DocStatus;
import com.enterprise.docqa.document.DocumentEntity;
import com.enterprise.docqa.document.DocumentRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.OffsetDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** M1W2-1 验收:对账规则(NOTIFIED>5min 重发 / PROCESSING>10min 查询并裁决) */
class ReconcileJobTest {

    private final DocumentRepository repo = mock(DocumentRepository.class);
    private final IngestClient client = mock(IngestClient.class);

    private ReconcileJob job() {
        ReconcileJob j = new ReconcileJob(repo, client);
        ReflectionTestUtils.setField(j, "callbackUrl", "http://cb");
        return j;
    }

    private DocumentEntity doc(DocStatus st, int minutesAgo) {
        DocumentEntity d = new DocumentEntity();
        d.setId(1L);
        d.setTitle("t");
        d.setFileName("a.pdf");
        d.setFilePath("p");
        d.setStatus(st);
        d.setUpdatedAt(OffsetDateTime.now().minusMinutes(minutesAgo));
        return d;
    }

    @Test
    void staleNotified_resendsIngest() {
        when(repo.findByStatusAndUpdatedAtBefore(any(), any())).thenReturn(List.of(doc(DocStatus.NOTIFIED, 6)))
                .thenReturn(List.of());
        job().reconcile();
        verify(client).notifyIngest(anyLong(), anyString(), anyString(), anyString(), anyString());
    }

    @Test
    void staleProcessing_reconcileReady() {
        DocumentEntity d = doc(DocStatus.PROCESSING, 11);
        when(repo.findByStatusAndUpdatedAtBefore(any(), any()))
                .thenReturn(List.of())
                .thenReturn(List.of(d));
        when(client.status(1L)).thenReturn(new IngestClient.IngestStatus(1, "READY", 8, null));
        job().reconcile();
        ArgumentCaptor<DocumentEntity> cap = ArgumentCaptor.forClass(DocumentEntity.class);
        verify(repo).save(cap.capture());
        assertThat(cap.getValue().getStatus()).isEqualTo(DocStatus.READY);
        assertThat(cap.getValue().getChunkCount()).isEqualTo(8);
    }

    @Test
    void staleProcessing_stillProcessing_onlyTouch() {
        DocumentEntity d = doc(DocStatus.PROCESSING, 11);
        when(repo.findByStatusAndUpdatedAtBefore(any(), any()))
                .thenReturn(List.of())
                .thenReturn(List.of(d));
        when(client.status(1L)).thenReturn(new IngestClient.IngestStatus(1, "PROCESSING", null, null));
        job().reconcile();
        ArgumentCaptor<DocumentEntity> cap = ArgumentCaptor.forClass(DocumentEntity.class);
        verify(repo).save(cap.capture());
        assertThat(cap.getValue().getStatus()).isEqualTo(DocStatus.PROCESSING);
    }

    @Test
    void staleProcessing_statusThrows_marksFailed() {
        DocumentEntity d = doc(DocStatus.PROCESSING, 11);
        when(repo.findByStatusAndUpdatedAtBefore(any(), any()))
                .thenReturn(List.of())
                .thenReturn(List.of(d));
        when(client.status(1L)).thenThrow(new BizException(5031, "down"));
        job().reconcile();
        ArgumentCaptor<DocumentEntity> cap = ArgumentCaptor.forClass(DocumentEntity.class);
        verify(repo).save(cap.capture());
        assertThat(cap.getValue().getStatus()).isEqualTo(DocStatus.FAILED);
    }

    @Test
    void nothingStale_noAction() {
        when(repo.findByStatusAndUpdatedAtBefore(any(), any())).thenReturn(List.of());
        job().reconcile();
        verify(client, never()).notifyIngest(anyLong(), anyString(), anyString(), anyString(), anyString());
    }
}
