import { defineFakeRoute } from "vite-plugin-fake-server/client";

export default defineFakeRoute([
  {
    url: "/get-async-routes",
    method: "get",
    response: () => {
      // 业务路由全部为静态路由(见 router/modules),无后端动态路由
      return {
        success: true,
        data: []
      };
    }
  }
]);
