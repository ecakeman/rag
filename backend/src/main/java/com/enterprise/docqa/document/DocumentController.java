package com.enterprise.docqa.document;

import com.enterprise.docqa.common.R;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService service;

    @PostMapping
    public R<DocumentDTO> upload(@RequestParam("file") MultipartFile file,
                                 @RequestParam(value = "title", required = false) String title) {
        return R.ok(DocumentDTO.of(service.upload(file, title)));
    }

    @GetMapping
    public R<Map<String, Object>> list(@RequestParam(required = false) String status,
                                       @RequestParam(required = false) String q,
                                       @RequestParam(defaultValue = "1") @Min(1) int page,
                                       @RequestParam(defaultValue = "10") @Min(1) @Max(100) int size) {
        var result = service.list(status, q, page, size);
        return R.ok(Map.of(
                "total", result.getTotalElements(),
                "records", result.getContent().stream().map(DocumentDTO::of).toList()));
    }

    @GetMapping("/{id}")
    public R<DocumentDTO> get(@PathVariable long id) {
        return R.ok(DocumentDTO.of(service.get(id)));
    }

    @DeleteMapping("/{id}")
    public R<Void> delete(@PathVariable long id) {
        service.delete(id);
        return R.ok();
    }

    public record DocumentDTO(long id, String title, String fileName, long fileSize, String status,
                              String errorMsg, int chunkCount, OffsetDateTime createdAt) {

        static DocumentDTO of(DocumentEntity d) {
            return new DocumentDTO(d.getId(), d.getTitle(), d.getFileName(), d.getFileSize(),
                    d.getStatus().name(), d.getErrorMsg(), d.getChunkCount(), d.getCreatedAt());
        }
    }
}
