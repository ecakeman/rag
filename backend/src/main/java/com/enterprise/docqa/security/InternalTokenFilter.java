package com.enterprise.docqa.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * /api/internal/** 的共享 token 校验(§6.1):与 Python 服务共享 INTERNAL_TOKEN。
 * 只拦截 internal 前缀,其余请求直接放行(交给 JWT 过滤器)。
 */
@Component
@Order(1)
public class InternalTokenFilter extends OncePerRequestFilter {

    private final String internalToken;

    public InternalTokenFilter(@Value("${ai.internal-token}") String internalToken) {
        this.internalToken = internalToken;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/internal/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String token = request.getHeader("X-Internal-Token");
        if (token == null || !token.equals(internalToken)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":401,\"message\":\"internal token 无效\",\"data\":null}");
            return;
        }
        chain.doFilter(request, response);
    }
}
