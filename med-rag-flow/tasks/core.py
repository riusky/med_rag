from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Callable, Optional, Set, TypeVar
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from prefect import task, get_run_logger
import inspect
import sys

T = TypeVar('T')

class TaskParameterModel(BaseModel):
    """所有任务参数的基类"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='forbid'
    )

class TaskDefinition:
    def __init__(self, key: str, description: str, func: Callable[..., T]):
        self.key = key
        self.description = description
        self.func = func
        self.param_model = self._create_param_model()

    def _create_param_model(self) -> Optional[type[BaseModel]]:
        """增强的参数模型生成方法"""
        sig = inspect.signature(self.func)
        fields = {}
        
        for name, param in sig.parameters.items():
            if name in ['self', 'cls']:
                continue
                
            # 处理Path类型注解
            annotation = param.annotation
            if getattr(annotation, '__origin__', None) is None and str(annotation).endswith('Path'):
                annotation = Path
                
            field_info = {
                'default': ... if param.default == param.empty else param.default,
                'annotation': annotation if annotation != param.empty else Any,
            }
            fields[name] = (field_info['annotation'], Field(**field_info))
        
        if not fields:
            return None
            
        return type(
            f'{self.func.__name__.title()}Params',
            (TaskParameterModel,),
            {'__annotations__': fields}
        )

    def execute(self, **kwargs) -> T:
        """执行任务并验证参数"""
        logger = get_run_logger()
        
        try:
            # 参数验证
            if self.param_model:
                validated = self.param_model(**kwargs).dict()
            else:
                validated = kwargs
                
            logger.info(f"🚀 执行任务 {self.key} (参数: {validated})")
            return self.func(**validated)
            
        except ValidationError as e:
            logger.error(f"❌ 参数验证失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ 任务执行失败: {str(e)}", exc_info=True)
            raise


class TaskRegistry:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._registry: Dict[str, TaskDefinition] = {}
            self._task_names: Set[str] = set()  # 用于检测任务名冲突
            self._initialized = True
            
    def register(self, key: str, description: str = "") -> Callable:
        """增强的注册装饰器"""
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            # 检查key冲突
            if key in self._registry:
                existing = self._registry[key]
                self._handle_duplicate_key(key, existing.func, func)
            
            # 检查Prefect任务名冲突
            task_name = func.__name__
            if task_name in self._task_names:
                self._handle_duplicate_task_name(task_name, func)
                
            # 注册任务
            task_def = TaskDefinition(key, description, func)
            self._registry[key] = task_def
            self._task_names.add(task_name)
            return func
        return decorator
      
    # def register(self, key: str, description: str, default_params: Dict[str, Any]):
    #     """增强的注册装饰器，包含冲突检测"""
    #     def decorator(func):
    #         # 检查key是否已存在
    #         if key in self._registry:
    #             self._handle_duplicate_key(key, func)
            
    #         # 检查Prefect任务名是否冲突
    #         task_name = func.__name__
    #         if task_name in self._task_names:
    #             self._handle_duplicate_task_name(task_name, func)
            
    #         # 注册任务
    #         self._registry[key] = TaskDefinition(
    #             key=key,
    #             description=description,
    #             parameters=default_params,
    #             function=func
    #         )
    #         self._task_names.add(task_name)
    #         return func
    #     return decorator
      
    def execute_task(self, task_key: str, params: Dict[str, Any] = None) -> Any:
        """动态执行任务"""
        if params is None:
            params = {}
            
        task_def = self.get(task_key)
        return task_def.execute(**params)

    def _handle_duplicate_key(self, key: str, existing_func: Callable, new_func: Callable):
        """处理key冲突"""
        error_msg = (
            f"任务key冲突! key '{key}' 已经被注册:\n"
            f"已有任务: {existing_func.__module__}.{existing_func.__name__}\n"
            f"新任务: {new_func.__module__}.{new_func.__name__}\n"
            "请修改其中一个任务的key"
        )
        self._fatal_error(error_msg)

    def _handle_duplicate_task_name(self, task_name: str, new_func: Callable):
        """处理Prefect任务名冲突"""
        existing = next(
            td for td in self._registry.values() 
            if td.func.__name__ == task_name  # 改为func
        )
        error_msg = (
            f"Prefect任务名冲突! 函数名 '{task_name}' 已经被使用:\n"
            f"已有任务: key={existing.key} ({existing.func.__module__})\n"  # 改为func
            f"新任务: key={new_func.__name__} ({new_func.__module__})\n"
            "请使用@task(name='唯一名称')指定不同的任务名"
        )
        self._fatal_error(error_msg)
    
    def _fatal_error(self, message: str):
        """输出错误并终止程序"""
        print(f"❌ 任务注册失败: {message}", file=sys.stderr)
        sys.exit(1)
    
    def get(self, key: str) -> TaskDefinition:
        if key not in self._registry:
            raise ValueError(f"未注册的任务: {key}. 可用任务: {list(self._registry.keys())}")
        return self._registry[key]
    
    @property
    def all_tasks(self) -> Dict[str, TaskDefinition]:
        return self._registry.copy()

# 全局单例实例
task_registry = TaskRegistry()

# 快捷方式
register_task = task_registry.register
get_task = task_registry.get
execute_task = task_registry.execute_task