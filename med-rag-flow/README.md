# Doc2Markdown Prefect Project
我现在要写一些 shell 文件来启动项目和停止项目

启动前端项目
cd ./frontend
bun install
npm install pm2 -g
pm2 start bun --name "med_rag_frontend" -- run dev


启动后端项目

cd  ../server
docker-compose up --build

启动工作流
cd ../med-rag-flow/flows
nohup python document_process_flow.py > output.log 2>&1 &