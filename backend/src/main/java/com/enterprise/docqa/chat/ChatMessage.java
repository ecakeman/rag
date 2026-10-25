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
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;

@Entity
@Table(name = "chat_message")
@Getter
@Setter
@NoArgsConstructor
public class ChatMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long sessionId;

    private String role;   // user / assistant

    private String content;

    /** JSONB: [{no,chunkId,docId,docTitle,sectionPath,page,text}] */
    @JdbcTypeCode(SqlTypes.JSON)
    private String citations;

    /** JSONB: [{node,status,detail,tsMs}] */
    @JdbcTypeCode(SqlTypes.JSON)
    private String trace;

    private Integer latencyMs;

    private OffsetDateTime createdAt;

    @PrePersist
    void prePersist() {
        createdAt = OffsetDateTime.now();
    }
}
