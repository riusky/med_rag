#!/bin/bash

# 启动前端项目
echo "Starting frontend..."
cd ../frontend
bun install
npm install pm2 -g

# 检查是否已存在同名PM2进程
if pm2 list | grep -q med_rag_frontend; then
    echo "Existing med_rag_frontend found, restarting..."
    pm2 delete med_rag_frontend
fi

pm2 start bun --name "med_rag_frontend" -- run dev
echo "Frontend started with PM2"

# 启动后端项目
echo "Starting backend..."
cd ../server
docker-compose up --build -d
echo "Backend started with Docker"

# 启动工作流
echo "Starting document processing flow..."
cd ../med-rag-flow/flows
conda activate simple_rag
# 检查是否已有进程在运行
if [ -f process.pid ] && ps -p $(cat process.pid) > /dev/null; then
    echo "Existing document process found (PID: $(cat process.pid)), killing it..."
    kill -9 $(cat process.pid)
    rm process.pid
fi

nohup python document_process_flow.py > output.log 2>&1 &
echo $! > process.pid
echo "Document processing flow started (PID: $(cat process.pid))"

echo "All services started successfully!"