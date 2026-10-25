const Layout = () => import("@/layout/index.vue");

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
        icon: "ep/folder-opened"
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
    }
  ]
} satisfies RouteConfigsTable;
