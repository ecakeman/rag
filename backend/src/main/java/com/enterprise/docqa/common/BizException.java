package com.enterprise.docqa.common;

public class BizException extends RuntimeException {

    private final int code;

    public BizException(int code, String message) {
        super(message);
        this.code = code;
    }

    public static BizException of(int code, String message) {
        return new BizException(code, message);
    }

    public int getCode() {
        return code;
    }
}
