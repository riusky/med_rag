from typing import Dict, Any, List
from prefect import flow, get_run_logger
from pydantic import BaseModel
from tasks import execute_task, task_registry

class TaskExecutionPlan(BaseModel):
    """任务执行计划定义"""
    task_key: str
    params: Dict[str, Any] = {}
    save_result_to: str = None  # 用于存储结果的变量名
    
    model_config = {
        "arbitrary_types_allowed": True  # 允许任意类型参数
    }

@flow(name="dynamic_task_orchestrator")
def execute_workflow(
    execution_plan: List[TaskExecutionPlan],
    initial_context: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """
    动态任务编排流程
    
    参数:
        execution_plan: 任务执行计划列表
        initial_context: 初始上下文变量
        
    返回:
        包含所有执行结果的上下文字典
    """
    logger = get_run_logger()
    context = initial_context.copy()
    
    logger.info(f"开始执行工作流，共 {len(execution_plan)} 个任务")
    
    for i, plan in enumerate(execution_plan, 1):
        try:
            # 增强的变量引用解析
            resolved_params = {}
            for param_name, param_value in plan.params.items():
                if isinstance(param_value, str) and param_value.startswith('$'):
                    var_name = param_value[1:]
                    if var_name not in context:
                        raise ValueError(f"上下文变量未找到: {var_name}")
                    resolved_params[param_name] = context[var_name]
                else:
                    resolved_params[param_name] = param_value
            
            logger.info(f"▶️ 执行任务 {i}/{len(execution_plan)}: {plan.task_key}")
            result = execute_task(plan.task_key, resolved_params)
            
            if plan.save_result_to:
                context[plan.save_result_to] = result
                logger.info(f"✅ 结果保存到: {plan.save_result_to}")
                
        except Exception as e:
            logger.error(f"❌ 任务执行失败: {plan.task_key} - {str(e)}")
            raise
    
    return context
  
  
""" 
条件执行
class ConditionalTaskPlan(TaskExecutionPlan):
    condition: str = None  # 例如 "$previous_task.success"

def enhanced_executor(plan: List[Union[TaskExecutionPlan, ConditionalTaskPlan]]):
    # 实现条件逻辑
    pass
  

并行执行
from prefect import flow, task

@flow
def parallel_workflow(plans: List[TaskExecutionPlan]):
    from prefect import futures
    results = []
    for plan in plans:
        future = futures.submit(execute_task, plan.task_key, plan.params)
        results.append(future)
    return [r.result() for r in results]  
    
    
从YAML/JSON加载配置
import yaml

def load_workflow_config(file_path: str) -> List[TaskExecutionPlan]:
    with open(file_path) as f:
        config = yaml.safe_load(f)
    return [
        TaskExecutionPlan(**step) 
        for step in config["steps"]
    ]
"""