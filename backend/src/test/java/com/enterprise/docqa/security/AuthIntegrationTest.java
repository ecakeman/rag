package com.enterprise.docqa.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * M1W1-2 验收:登录成功/密码错 401/受保护接口无 token 401/带 token 200。
 * 依赖 compose 内 PG(db:5432),在 app 容器内运行。
 */
@SpringBootTest
@AutoConfigureMockMvc
class AuthIntegrationTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    ObjectMapper om;

    @Test
    void login_ok_returns_token() throws Exception {
        MvcResult res = mvc.perform(post("/api/auth/login")
                        .contentType("application/json")
                        .content("{\"username\":\"admin\",\"password\":\"admin123\"}"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode body = om.readTree(res.getResponse().getContentAsString());
        assertThat(body.get("code").asInt()).isZero();
        assertThat(body.at("/data/token").asText()).isNotBlank();
        assertThat(body.at("/data/username").asText()).isEqualTo("admin");
    }

    @Test
    void login_wrongPassword_401() throws Exception {
        mvc.perform(post("/api/auth/login")
                        .contentType("application/json")
                        .content("{\"username\":\"admin\",\"password\":\"bad\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void protectedApi_withoutToken_401() throws Exception {
        mvc.perform(get("/api/documents")).andExpect(status().isUnauthorized());
    }

    @Test
    void protectedApi_withToken_200() throws Exception {
        MvcResult login = mvc.perform(post("/api/auth/login")
                .contentType("application/json")
                .content("{\"username\":\"admin\",\"password\":\"admin123\"}")).andReturn();
        String token = om.readTree(login.getResponse().getContentAsString()).at("/data/token").asText();

        mvc.perform(get("/api/documents").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());
    }

    @Test
    void login_blankField_422() throws Exception {
        mvc.perform(post("/api/auth/login")
                        .contentType("application/json")
                        .content("{\"username\":\"\",\"password\":\"x\"}"))
                .andExpect(status().isUnprocessableEntity());
    }
}
