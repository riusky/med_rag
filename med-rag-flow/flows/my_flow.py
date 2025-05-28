from prefect import flow
from tasks.core import get_task,task_registry

# @flow
def process_documents_flow():
    # 获取所有已注册任务
    all_task = task_registry.all_tasks
    print(all_task)