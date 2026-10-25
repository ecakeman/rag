package com.enterprise.docqa.common;

public record R<T>(int code, String message, T data) {

    public static <T> R<T> ok(T data) {
        return new R<>(0, "ok", data);
    }

    public static R<Void> ok() {
        return new R<>(0, "ok", null);
    }

    public static <T> R<T> error(int code, String message) {
        return new R<>(code, message, null);
    }
}
