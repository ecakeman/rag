const Layout = () => import("@/layout/index.vue");

export default {
  path: "/search",
  name: "Search",
  component: Layout,
  redirect: "/search/index",
  meta: {
    title: "智能检索",
    icon: "ep/search",
    rank: 3
  },
  children: [
    {
      path: "/search/index",
      name: "SearchIndex",
      component: () => import("@/views/search/index.vue"),
      meta: { title: "智能检索" }
    }
  ]
} satisfies RouteConfigsTable;
