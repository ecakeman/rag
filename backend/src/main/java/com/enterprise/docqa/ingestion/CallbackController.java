package com.enterprise.docqa.ingestion;

import com.enterprise.docqa.document.DocumentService;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Python 回调接收端(§5.2);由 InternalTokenFilter 校验 X-Internal-Token */
@RestController
@RequestMapping("/api/internal/ingest")
@RequiredArgsConstructor
public class CallbackController {

    private final DocumentService documentService;

    @PostMapping("/callback")
    public ResponseEntity<Void> callback(@RequestBody CallbackBody body) {
        documentService.applyCallback(body.getDocId(), body.getStatus(),
                body.getChunkCount(), body.getErrorMsg());
        return ResponseEntity.noContent().build();
    }

    @Data
    public static class CallbackBody {
        @NotNull
        private Long docId;
        @NotNull
        private String status;
        private Integer chunkCount;
        private String errorMsg;
    }
}
