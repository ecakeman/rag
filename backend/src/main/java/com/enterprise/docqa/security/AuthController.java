package com.enterprise.docqa.security;

import com.enterprise.docqa.common.BizException;
import com.enterprise.docqa.common.R;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final SysUserRepository userRepository;
    private final JwtService jwtService;
    private final PasswordEncoder passwordEncoder;

    @PostMapping("/login")
    public R<Map<String, String>> login(@Valid @RequestBody LoginRequest req) {
        SysUser user = userRepository.findByUsername(req.getUsername())
                .orElseThrow(() -> BizException.of(401, "用户名或密码错误"));
        if (!passwordEncoder.matches(req.getPassword(), user.getPasswordHash())) {
            throw BizException.of(401, "用户名或密码错误");
        }
        return R.ok(Map.of(
                "token", jwtService.issue(user.getId(), user.getUsername()),
                "username", user.getUsername()));
    }
}
