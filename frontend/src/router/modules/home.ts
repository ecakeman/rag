const Layout = () => import("@/layout/index.vue");

/**
 * 根路由(pure-admin-thin 的 formatTwoStageRoutes 依赖 path:"/" 的根路由,
 * 其余模块会被拍平塞进它的 children,缺失会导致整棵路由树被静默丢弃)
 */
export default {
  path: "/",
  name: "Home",
  component: Layout,
  redirect: "/docs",
  meta: {
    icon: "ep/home-filled",
    title: "首页",
    rank: 0
  },
  children: [
    {
      path: "/docs",
      name: "Docs",
      component: () => import("@/views/docs/index.vue"),
      meta: {
        title: "文档管理",
        icon: "ep/folder-opened",
        keepAlive: true
      }
    },
    {
      path: "/chat",
      name: "Chat",
      component: () => import("@/views/chat/index.vue"),
      meta: {
        title: "知识问答",
        icon: "ep/chat-dot-round"
      }
    },
    {
      path: "/search",
      name: "Search",
      component: () => import("@/views/search/index.vue"),
      meta: {
        title: "智能检索",
        icon: "ep/search"
      }
    },
    {
      path: "/settings",
      name: "Settings",
      component: () => import("@/views/settings/index.vue"),
      meta: {
        title: "系统设置",
        icon: "ep/setting"
      }
    }
  ]
} satisfies RouteConfigsTable;
