package com.enterprise.docqa.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Date;

@Component
public class JwtService {

    private final SecretKey key;
    private final Duration ttl;

    public JwtService(@Value("${app.jwt-secret}") String secret,
                      @Value("${app.jwt-ttl}") Duration ttl) {
        byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 32) {
            throw new IllegalStateException("app.jwt-secret 必须至少 32 字节");
        }
        this.key = Keys.hmacShaKeyFor(bytes);
        this.ttl = ttl;
    }

    public String issue(Long uid, String username) {
        Date now = new Date();
        return Jwts.builder()
                .subject(String.valueOf(uid))
                .claim("username", username)
                .claim("role", "ADMIN")
                .issuedAt(now)
                .expiration(new Date(now.getTime() + ttl.toMillis()))
                .signWith(key)
                .compact();
    }

    /** @return 解析后的 claims;非法/过期抛 JwtException */
    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build()
                .parseSignedClaims(token).getPayload();
    }

    public boolean isValid(String token) {
        try {
            parse(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }
}
