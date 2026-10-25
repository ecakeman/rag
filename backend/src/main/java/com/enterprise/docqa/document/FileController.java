package com.enterprise.docqa.document;

import com.enterprise.docqa.common.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Map;

/** 原件下载(DESIGN §5.1 可选项,落地实现) */
@RestController
@RequestMapping("/api/files")
@RequiredArgsConstructor
public class FileController {

    private static final Map<String, MediaType> TYPES = Map.of(
            "pdf", MediaType.APPLICATION_PDF,
            "docx", MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "md", new MediaType(MediaType.TEXT_PLAIN, StandardCharsets.UTF_8),
            "txt", new MediaType(MediaType.TEXT_PLAIN, StandardCharsets.UTF_8));

    private final DocumentRepository repo;

    @GetMapping("/{id}")
    public ResponseEntity<FileSystemResource> download(@PathVariable long id) {
        var doc = repo.findById(id)
                .orElseThrow(() -> BizException.of(404, "文档不存在: " + id));
        Path path = Path.of(doc.getFilePath());
        if (!path.isAbsolute()) {
            path = Path.of("/workspaces/enterprise-doc-qa", doc.getFilePath());
        }
        if (!path.toFile().exists()) {
            throw BizException.of(404, "文件已不存在: " + doc.getFileName());
        }
        String encoded = URLEncoder.encode(doc.getFileName(), StandardCharsets.UTF_8)
                .replace("+", "%20");
        MediaType type = TYPES.getOrDefault(
                doc.getFileName().contains(".")
                        ? doc.getFileName().substring(doc.getFileName().lastIndexOf('.') + 1).toLowerCase()
                        : "",
                MediaType.APPLICATION_OCTET_STREAM);
        return ResponseEntity.ok()
                .contentType(type)
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename*=UTF-8''" + encoded)
                .body(new FileSystemResource(path));
    }
}
