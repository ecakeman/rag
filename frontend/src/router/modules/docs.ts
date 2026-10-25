const Layout = () => import("@/layout/index.vue");

export default {
  path: "/docs",
  name: "Docs",
  component: Layout,
  redirect: "/docs/index",
  meta: {
    title: "文档管理",
    icon: "ep/folder-opened",
    rank: 1
  },
  children: [
    {
      path: "/docs/index",
      name: "DocsIndex",
      component: () => import("@/views/docs/index.vue"),
      meta: { title: "文档管理", keepAlive: true }
    }
  ]
} satisfies RouteConfigsTable;
