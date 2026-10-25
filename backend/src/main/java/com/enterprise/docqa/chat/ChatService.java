package com.enterprise.docqa.chat;

import com.enterprise.docqa.common.BizException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class ChatService {

    private final ChatSessionRepository sessionRepository;
    private final ChatMessageRepository messageRepository;
    private final ObjectMapper om;

    @Value("${app.chat-history-messages}")
    private int historyMessages;

    public ChatSession createSession(String title, String firstMessage) {
        ChatSession s = new ChatSession();
        if (firstMessage != null && !firstMessage.isBlank()) {
            s.setTitle(firstMessage.length() > 20 ? firstMessage.substring(0, 20) : firstMessage);
        } else {
            s.setTitle(title);
        }
        return sessionRepository.save(s);
    }

    public List<ChatSession> listSessions() {
        return sessionRepository.findAll(org.springframework.data.domain.Sort.by(
                org.springframework.data.domain.Sort.Direction.DESC, "id"));
    }

    public ChatSession requireSession(long id) {
        return sessionRepository.findById(id)
                .orElseThrow(() -> BizException.of(404, "会话不存在: " + id));
    }

    public List<ChatMessage> messages(long sessionId) {
        requireSession(sessionId);
        return messageRepository.findBySessionIdOrderByIdAsc(sessionId);
    }

    public long saveUserMessage(long sessionId, String content) {
        ChatMessage m = new ChatMessage();
        m.setSessionId(sessionId);
        m.setRole("user");
        m.setContent(content);
        long id = messageRepository.save(m).getId();
        // 首条用户消息覆盖默认标题(§4.2)
        sessionRepository.findById(sessionId).ifPresent(s -> {
            if ("新会话".equals(s.getTitle())) {
                String t = content.length() > 20 ? content.substring(0, 20) : content;
                s.setTitle(t.length() > 128 ? t.substring(0, 128) : t);
                sessionRepository.save(s);
            }
        });
        return id;
    }

    public void deleteSession(long sessionId) {
        requireSession(sessionId);
        messageRepository.deleteAll(messageRepository.findBySessionIdOrderByIdAsc(sessionId));
        sessionRepository.deleteById(sessionId);
    }

    public Long saveAssistantMessage(long sessionId, String content, String citationsJson,
                                     List<String> traceEvents, Integer latencyMs) {
        ChatMessage m = new ChatMessage();
        m.setSessionId(sessionId);
        m.setRole("assistant");
        m.setContent(content);
        try {
            if (citationsJson != null) {
                m.setCitations(om.writeValueAsString(om.readTree(citationsJson)));
            }
            if (traceEvents != null && !traceEvents.isEmpty()) {
                m.setTrace(om.writeValueAsString(traceEvents.stream()
                        .map(t -> {
                            try {
                                return om.readTree(t);
                            } catch (Exception e) {
                                return om.createObjectNode();
                            }
                        }).toList()));
            }
        } catch (Exception ignored) {
        }
        m.setLatencyMs(latencyMs);
        return messageRepository.save(m).getId();
    }

    public boolean hasAssistantMessage(long sessionId, long afterMessageId) {
        return messageRepository.findBySessionIdOrderByIdAsc(sessionId).stream()
                .anyMatch(m -> m.getId() > afterMessageId && "assistant".equals(m.getRole()));
    }

    /** 组装 Python /chat 请求体(§5.2),带最近 N 条历史 */
    public String buildPythonChatBody(long sessionId, long messageId, String message) {
        List<ChatMessage> all = messageRepository.findBySessionIdOrderByIdAsc(sessionId);
        List<ChatMessage> history = all.stream()
                .filter(m -> m.getId() < messageId)
                .skip(Math.max(0, all.stream().filter(x -> x.getId() < messageId).count()
                        - historyMessages))
                .toList();
        try {
            var historyNodes = history.stream()
                    .map(m -> Map.of("role", m.getRole(), "content", m.getContent()))
                    .toList();
            return om.writeValueAsString(Map.of(
                    "sessionId", sessionId,
                    "messageId", messageId,
                    "message", message,
                    "history", historyNodes));
        } catch (Exception e) {
            throw new BizException(500, "请求体组装失败");
        }
    }
}
