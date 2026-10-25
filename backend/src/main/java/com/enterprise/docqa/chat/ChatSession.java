package com.enterprise.docqa.chat;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.OffsetDateTime;

@Entity
@Table(name = "chat_session")
@Getter
@Setter
@NoArgsConstructor
public class ChatSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String title;

    private OffsetDateTime createdAt;

    @PrePersist
    void prePersist() {
        if (title == null || title.isBlank()) {
            title = "新会话";
        }
        if (title.length() > 128) {
            title = title.substring(0, 128);
        }
        createdAt = OffsetDateTime.now();
    }
}
