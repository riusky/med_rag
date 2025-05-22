# med_rag_frontend

> 基于生成式AI的医疗知识检索与问答系统前端，遵循现代化Web开发最佳实践

## 功能特性

- 🚀 使用 [Vue 3](https://vuejs.org/) 的组合式 API 和 `<script setup>` 语法
- 🔧 采用 [TypeScript](https://www.typescriptlang.org/) 实现类型安全
- ⚡️ 使用 [Vite](https://vitejs.dev/) 实现快速开发和优化构建
- 📦 集成 [Pinia](https://pinia.vuejs.org/) 状态管理
- 🔄 配置 [Vue Router](https://router.vuejs.org/) 实现客户端路由
- 🧪 使用 [Vitest](https://vitest.dev/) 的测试环境
- 🎨 支持 SCSS 预处理
- 📱 响应式设计工具
- 🔒 认证流程实现
- 🧩 组件架构最佳实践

## 快速开始

### 环境要求

- Bun

### 安装步骤

```bash
cd frontend

# 安装依赖
bun install

# 启动开发服务器
bun run dev
```

### 生产环境构建

```bash
bun run build
```

### docker 启动

```bash

## 生产环境（使用默认配置）
docker-compose up -d --build

# 清理旧容器
docker-compose -f docker-compose.dev.yml down -v

# 启动开发环境
docker-compose -f docker-compose.dev.yml up --build

# 验证访问
curl http://localhost:5173

```

## 项目结构

```
├── public/              # 静态资源
├── src/
│   ├── api/            # API 服务层
│   ├── assets/         # 构建处理的资源文件
│   ├── components/     # 可复用 Vue 组件
│   ├── layouts/        # 布局组件
│   ├── plugins/        # Vue 插件和扩展
│   ├── router/         # Vue Router 配置
│   ├── stores/         # Pinia 状态存储
│   ├── types/          # TypeScript 类型定义
│   ├── utils/          # 工具函数
│   ├── pages/          # 页面组件
│   ├── App.vue         # 根组件
│   └── main.ts         # 应用入口文件
├── eslint.config.ts    # ESLint 配置
├── .gitignore          # Git 忽略规则
├── index.html          # HTML 入口文件
├── package.json        # 项目依赖和脚本
├── tsconfig.json       # TypeScript 配置
├── vite.config.ts      # Vite 配置
├── bun.lockb           # Bun 锁定文件
└── README.md           # 项目文档
```

## 文档参考

Vue 3 详细文档请参阅 [Vue.js 官方文档](https://vuejs.org/guide/introduction.html)。

Vue 中的 TypeScript 使用指南请参考 [Vue TypeScript 指南](https://vuejs.org/guide/typescript/overview.html)。


