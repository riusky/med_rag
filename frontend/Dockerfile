# 使用官方 Bun 镜像作为构建环境
FROM oven/bun:1.1.21 as builder

WORKDIR /app

# 优先复制包管理文件以利用 Docker 缓存
COPY package.json bun.lockb bunfig.toml ./
RUN bun install --frozen-lockfile

# 复制项目文件
COPY . .

# 构建项目
RUN bun run build

# 使用 Nginx 作为生产服务器
FROM nginx:1.25-alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置（如果需要）
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]



# 新增开发阶段
FROM oven/bun:1.1.21 as development

WORKDIR /app
COPY package.json bun.lockb bunfig.toml ./
RUN bun install --frozen-lockfile

# 不要执行 build 命令
# 保持容器运行开发服务器
CMD ["bun", "run", "dev"]