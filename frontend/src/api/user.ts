import { http } from "@/utils/http";

export type UserResult = {
  success: boolean;
  data: {
    /** 头像 */
    avatar: string;
    /** 用户名 */
    username: string;
    /** 昵称 */
    nickname: string;
    /** 当前登录用户的角色 */
    roles: Array<string>;
    /** 按钮级别权限 */
    permissions: Array<string>;
    /** `token` */
    accessToken: string;
    /** 用于调用刷新`accessToken`的接口时所需的`token` */
    refreshToken: string;
    /** `accessToken`的过期时间(毫秒时间戳) */
    expires: Date;
  };
};

export type RefreshTokenResult = {
  success: boolean;
  data: {
    accessToken: string;
    refreshToken: string;
    expires: Date;
  };
};

/**
 * 登录 — 对接后端 POST /api/auth/login(响应体 R{code,message,data:{token,username}}),
 * 此处映射为 pure-admin 的 UserResult 结构。24h 与后端 JWT TTL 一致。
 */
export const getLogin = (data?: object) => {
  return http
    .request<{ code: number; message: string; data: { token: string; username: string } }>(
      "post",
      "/api/auth/login",
      { data }
    )
    .then(res => {
      if (res.code !== 0 || !res.data?.token) {
        return Promise.reject(new Error(res.message || "登录失败"));
      }
      return {
        success: true,
        data: {
          avatar: "",
          username: res.data.username,
          nickname: res.data.username,
          roles: ["admin"],
          permissions: ["*:*:*"],
          accessToken: res.data.token,
          refreshToken: res.data.token,
          expires: new Date(Date.now() + 24 * 3600 * 1000)
        }
      } as UserResult;
    });
};

/** 刷新`token`(暂用 mock;后端无刷新接口,JWT 24h 有效期内无需刷新) */
export const refreshTokenApi = (data?: object) => {
  return http.request<RefreshTokenResult>("post", "/refresh-token", { data });
};
