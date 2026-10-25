package com.enterprise.docqa.chat;

import com.enterprise.docqa.common.R;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;
    private final SseGateway sseGateway;

    @PostMapping("/sessions")
    public R<Map<String, Object>> createSession(@RequestBody(required = false) SessionBody body) {
        var s = chatService.createSession(body == null ? null : body.getTitle(),
                body == null ? null : body.getFirstMessage());
        return R.ok(Map.of("sessionId", s.getId(), "title", s.getTitle()));
    }

    @GetMapping("/sessions")
    public R<List<SessionDTO>> sessions() {
        return R.ok(chatService.listSessions().stream()
                .map(s -> new SessionDTO(s.getId(), s.getTitle(), s.getCreatedAt()))
                .toList());
    }

    @GetMapping("/sessions/{id}/messages")
    public R<List<MessageDTO>> messages(@PathVariable long id) {
        return R.ok(chatService.messages(id).stream().map(MessageDTO::of).toList());
    }

    @DeleteMapping("/sessions/{id}")
    public R<Void> deleteSession(@PathVariable long id) {
        chatService.deleteSession(id);
        return R.ok();
    }

    /** SSE 流:meta 由本端先发(SseEmitter 早期缓冲保证顺序,§5.3),其余透传 Python */
    @PostMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@RequestBody ChatBody body) {
        var session = chatService.requireSession(body.getSessionId());
        long messageId = chatService.saveUserMessage(session.getId(), body.getMessage());
        SseEmitter emitter = sseGateway.newEmitter();
        try {
            emitter.send(SseEmitter.event().name("meta")
                    .data("{\"sessionId\":" + session.getId() + ",\"userMessageId\":" + messageId + "}",
                            MediaType.APPLICATION_JSON));
        } catch (Exception ignored) {
        }
        sseGateway.stream(emitter, session.getId(), messageId, body.getMessage());
        return emitter;
    }

    @Data
    public static class SessionBody {
        private String title;
        private String firstMessage;
    }

    public record SessionDTO(long sessionId, String title, java.time.OffsetDateTime createdAt) {
    }

    @Data
    public static class ChatBody {
        private long sessionId;
        @NotBlank
        private String message;
    }

    public record MessageDTO(long id, String role, String content,
                             Object citations, Object trace, Integer latencyMs) {
        static MessageDTO of(ChatMessage m) {
            return new MessageDTO(m.getId(), m.getRole(), m.getContent(),
                    jsonOrNull(m.getCitations()), jsonOrNull(m.getTrace()), m.getLatencyMs());
        }

        private static Object jsonOrNull(String json) {
            if (json == null) {
                return null;
            }
            try {
                return new com.fasterxml.jackson.databind.ObjectMapper().readTree(json);
            } catch (Exception e) {
                return json;
            }
        }
    }
}
