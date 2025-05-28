from executor import execute_workflow, TaskExecutionPlan
from pprint import pprint

# 示例1: 直接执行任务序列
simple_plan = [
    TaskExecutionPlan(
        task_key="text_lower",
        params={"text": "Hello, WORLD!"},
        save_result_to="text_lower"
    ),
    TaskExecutionPlan(
        task_key="text_upper",
        params={
            "text": "$print_text",
        },
        save_result_to="text_lower"
    )
]

if __name__ == "__main__":
    # 执行工作流
    result = execute_workflow(simple_plan)
    
    print("\n最终上下文:")
    pprint(result)
    
    # 示例2: 从配置文件加载
    config = {
        "workflows": {
            "text_processing": [
                {
                    "task": "text_lower",
                    "params": {"text": "Another EXAMPLE."},
                    "save_as": "text_lower"
                },
                {
                    "task": "text_upper",
                    "params": {"text": "$print_text"},
                    "save_as": "text_upper"
                }
            ]
        }
    }
    
    # 转换配置为执行计划
    advanced_plan = [
        TaskExecutionPlan(
            task_key=step["task"],
            params=step["params"],
            save_result_to=step.get("save_as")
        )
        for step in config["workflows"]["text_processing"]
    ]
    
    execute_workflow(advanced_plan)