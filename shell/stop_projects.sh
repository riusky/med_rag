#!/bin/bash

# 停止前端
echo "Stopping frontend..."
if pm2 list | grep -q med_rag_frontend; then
    pm2 stop med_rag_frontend
    pm2 delete med_rag_frontend
    echo "Frontend stopped"
else
    echo "No med_rag_frontend process found"
fi

# 停止后端
echo "Stopping backend..."
cd ../server
docker-compose down
echo "Backend stopped"

# 停止工作流
echo "Stopping document processing flow..."
cd ../med-rag-flow/flows
if [ -f process.pid ]; then
    if ps -p $(cat process.pid) > /dev/null; then
        kill -9 $(cat process.pid)
        echo "Document processing flow stopped (PID: $(cat process.pid))"
    else
        echo "Process $(cat process.pid) not found"
    fi
    rm process.pid
else
    echo "No process.pid found - is the flow running?"
fi

echo "All services stopped successfully!"