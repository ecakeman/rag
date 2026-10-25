package com.enterprise.docqa.chat;

import com.enterprise.docqa.document.DocumentRepository;
import com.enterprise.docqa.document.DocStatus;
import com.enterprise.docqa.document.DocumentEntity;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** 前后端兼容整改新增端点:会话删除/标题自动覆盖/原件下载 */
@SpringBootTest
@AutoConfigureMockMvc
class ChatExtrasTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    ChatService chatService;

    @Autowired
    ChatSessionRepository sessionRepository;

    @Autowired
    DocumentRepository documentRepository;

    private String token() throws Exception {
        String body = mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                        .post("/api/auth/login")
                        .contentType("application/json")
                        .content("{\"username\":\"admin\",\"password\":\"admin123\"}"))
                .andReturn().getResponse().getContentAsString();
        return new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(body).at("/data/token").asText();
    }

    @Test
    void sessionTitleOverwrittenByFirstMessage() {
        var s = chatService.createSession(null, null);
        assertThat(s.getTitle()).isEqualTo("新会话");
        chatService.saveUserMessage(s.getId(), "工作满三年的年假有几天天哪这个问题好长");
        assertThat(sessionRepository.findById(s.getId()).orElseThrow().getTitle())
                .hasSizeLessThanOrEqualTo(20)
                .startsWith("工作满三年");
        // 第二条消息不覆盖
        chatService.saveUserMessage(s.getId(), "第二个问题");
        assertThat(sessionRepository.findById(s.getId()).orElseThrow().getTitle())
                .startsWith("工作满三年");
        sessionRepository.deleteById(s.getId());
    }

    @Test
    void deleteSessionCascade() throws Exception {
        var s = chatService.createSession(null, null);
        chatService.saveUserMessage(s.getId(), "q");
        String jwt = token();
        mvc.perform(delete("/api/chat/sessions/" + s.getId())
                        .header("Authorization", "Bearer " + jwt))
                .andExpect(status().isOk());
        mvc.perform(get("/api/chat/sessions/" + s.getId() + "/messages")
                        .header("Authorization", "Bearer " + jwt))
                .andExpect(status().isNotFound());
    }

    @Test
    void downloadOriginalFile() throws Exception {
        Path dir = Path.of("/workspaces/enterprise-doc-qa/data/files");
        Files.createDirectories(dir);
        Path file = dir.resolve("download-test-1.md");
        Files.writeString(file, "# 下载测试\n内容");

        DocumentEntity d = new DocumentEntity();
        d.setTitle("下载测试");
        d.setFileName("下载测试.md");
        d.setFilePath("data/files/download-test-1.md");
        d.setFileSize(Files.size(file));
        d.setStatus(DocStatus.READY);
        d = documentRepository.save(d);

        String jwt = token();
        var res = mvc.perform(get("/api/files/" + d.getId())
                        .header("Authorization", "Bearer " + jwt))
                .andExpect(status().isOk())
                .andReturn();
        assertThat(res.getResponse().getHeader("Content-Disposition")).contains(".md");
        assertThat(res.getResponse().getContentAsByteArray())
                .asString(java.nio.charset.StandardCharsets.UTF_8)
                .contains("下载测试");

        documentRepository.deleteById(d.getId());
        Files.deleteIfExists(file);
    }
}
