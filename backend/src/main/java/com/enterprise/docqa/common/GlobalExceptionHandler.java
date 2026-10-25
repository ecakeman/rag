package com.enterprise.docqa.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BizException.class)
    public ResponseEntity<R<Void>> handleBiz(BizException e) {
        return ResponseEntity.status(httpStatusOf(e.getCode())).body(R.error(e.getCode(), e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<R<Void>> handleValidation(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .findFirst().orElse("参数错误");
        return ResponseEntity.status(422).body(R.error(422, msg));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<R<Void>> handleOther(Exception e) {
        log.error("unhandled", e);
        return ResponseEntity.status(500).body(R.error(500, "服务内部错误"));
    }

    private int httpStatusOf(int code) {
        return switch (code) {
            case 401, 403, 404, 409, 422 -> code;
            case 5031, 5032 -> 503;
            default -> 500;
        };
    }
}
