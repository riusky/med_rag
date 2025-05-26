export default [
  {
    path: '/',
    component: () => import('@/pages/index2.vue'),
    name: 'home',
    meta: {
      layout: 'AppLayout',
      auth: true,
    },
  },
  {
    path: '/knowledge/:param(\\d+)?',
    component: () => import('@/pages/index3.vue'),
    name: 'ecommerce',
    meta: {
      layout: 'AppLayout',
      auth: true,
    },
    props: (route) => ({
      param: route.params.param ? Number(route.params.param) : null // 手动转换类型
    })
  },
  {
    path: '/document',
    component: () => import('@/pages/index4.vue'),
    name: 'crypto',
    meta: {
      layout: 'AppLayout',
      auth: true,
    },
  },
  {
    // callback route
    path: '/:path(.*)*',
    component: () => import('@/pages/callback.vue'),
    name: 'callback',
  },
]
