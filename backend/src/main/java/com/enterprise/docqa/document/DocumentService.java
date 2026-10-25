package com.enterprise.docqa.document;

import com.enterprise.docqa.common.BizException;
import com.enterprise.docqa.ingestion.IngestClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentService {

    private final DocumentRepository repo;
    private final FileStorage storage;
    private final IngestClient ingestClient;
    private final CurrentUser currentUser;

    @Value("${ai.callback-url}")
    private String callbackUrl;

    public DocumentEntity upload(MultipartFile file, String title) {
        String fileName = file.getOriginalFilename();
        storage.checkAllowed(fileName);

        DocumentEntity doc = new DocumentEntity();
        doc.setFileName(fileName);
        doc.setTitle(title != null && !title.isBlank() ? title : stripExt(fileName));
        doc.setFileSize(file.getSize());
        doc.setMimeType(file.getContentType());
        doc.setStatus(DocStatus.UPLOADED);
        doc.setCreatedBy(currentUser.uidOrNull());
        doc.setFilePath("PENDING"); // file_path 非空约束;落盘后立即更新为 {id}.{ext}
        doc = repo.save(doc);

        String path = storage.store(doc.getId(), file);
        doc.setFilePath(path);

        try {
            ingestClient.notifyIngest(doc.getId(), path, fileName, doc.getTitle(), callbackUrl);
            doc.setStatus(DocStatus.NOTIFIED);
        } catch (BizException e) {
            doc.setStatus(DocStatus.FAILED);
            doc.setErrorMsg("通知AI服务失败: " + e.getMessage());
        }
        return repo.save(doc);
    }

    public DocumentEntity get(long id) {
        return repo.findById(id).orElseThrow(() -> BizException.of(404, "文档不存在: " + id));
    }

    public Page<DocumentEntity> list(String status, String q, int page, int size) {
        PageRequest pageable = PageRequest.of(Math.max(page - 1, 0), Math.min(size, 100),
                Sort.by(Sort.Direction.DESC, "createdAt"));
        DocStatus st = status == null || status.isBlank() ? null : DocStatus.valueOf(status);
        if (st != null && q != null && !q.isBlank()) {
            return repo.findByStatusAndTitleContainingIgnoreCase(st, q, pageable);
        }
        if (st != null) {
            return repo.findByStatus(st, pageable);
        }
        if (q != null && !q.isBlank()) {
            return repo.findByTitleContainingIgnoreCase(q, pageable);
        }
        return repo.findAll(pageable);
    }

    public void delete(long id) {
        DocumentEntity doc = get(id);
        if (doc.getStatus() == DocStatus.READY || doc.getStatus() == DocStatus.FAILED
                || doc.getStatus() == DocStatus.NOTIFIED) {
            try {
                ingestClient.deleteChunks(id);
            } catch (BizException e) {
                throw BizException.of(409, "AI 服务暂不可用,删除失败请稍后重试");
            }
        }
        repo.delete(doc);
        if (doc.getFilePath() != null) {
            storage.delete(doc.getFilePath());
        }
    }

    /** 回调驱动状态迁移(§4.4) */
    public DocumentEntity applyCallback(long docId, String status, Integer chunkCount, String errorMsg) {
        DocumentEntity doc = get(docId);
        switch (status) {
            case "PROCESSING" -> {
                doc.setStatus(DocStatus.PROCESSING);
                doc.setErrorMsg(null);
            }
            case "READY" -> {
                doc.setStatus(DocStatus.READY);
                doc.setErrorMsg(null);
                if (chunkCount != null) {
                    doc.setChunkCount(chunkCount);
                }
            }
            case "FAILED" -> {
                doc.setStatus(DocStatus.FAILED);
                doc.setErrorMsg(errorMsg == null ? "AI 服务处理失败" : errorMsg);
            }
            default -> throw BizException.of(422, "未知回调状态: " + status);
        }
        return repo.save(doc);
    }

    private static String stripExt(String name) {
        int i = name.lastIndexOf('.');
        return i <= 0 ? name : name.substring(0, i);
    }
}
