package com.enterprise.docqa.document;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

@Component
public class FileStorage {

    private static final Set<String> ALLOWED_EXT = Set.of("pdf", "docx", "md", "txt");

    private final Path baseDir;

    public FileStorage(@Value("${app.file-dir}") String dir) {
        this.baseDir = Path.of(dir);
    }

    public String extOf(String fileName) {
        int i = fileName.lastIndexOf('.');
        return i < 0 ? "" : fileName.substring(i + 1).toLowerCase();
    }

    public void checkAllowed(String fileName) {
        if (!ALLOWED_EXT.contains(extOf(fileName))) {
            throw new com.enterprise.docqa.common.BizException(422,
                    "仅支持 pdf/docx/md/txt 格式,收到: " + fileName);
        }
    }

    /** 存为 {dir}/{docId}.{ext},返回相对路径 */
    public String store(long docId, MultipartFile file) {
        try {
            Files.createDirectories(baseDir);
            String ext = extOf(file.getOriginalFilename());
            Path target = baseDir.resolve(docId + "." + ext);
            file.transferTo(target);
            return target.toString().replace("\\", "/");
        } catch (IOException e) {
            throw new com.enterprise.docqa.common.BizException(500, "文件保存失败: " + e.getMessage());
        }
    }

    public void delete(String relativePath) {
        try {
            Files.deleteIfExists(Path.of(relativePath));
        } catch (IOException ignored) {
        }
    }
}
