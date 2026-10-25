const Layout = () => import("@/layout/index.vue");

export default {
  path: "/chat",
  name: "Chat",
  component: Layout,
  redirect: "/chat/index",
  meta: {
    title: "知识问答",
    icon: "ep/chat-dot-round",
    rank: 2
  },
  children: [
    {
      path: "/chat/index",
      name: "ChatIndex",
      component: () => import("@/views/chat/index.vue"),
      meta: { title: "知识问答", keepAlive: true }
    }
  ]
} satisfies RouteConfigsTable;
