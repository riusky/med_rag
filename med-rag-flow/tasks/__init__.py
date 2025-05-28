# tasks/__init__.py
import importlib
from pathlib import Path
import sys
from typing import List
import re

def _normalize_module_path(path: Path, base_dir: Path) -> str:
    """
    将文件路径转换为合法的Python模块路径
    例如: tasks\chunking\markdown.py → tasks.chunking.markdown
    """
    # 获取相对于tasks目录的路径
    relative_path = path.relative_to(base_dir)
    
    # 转换为模块格式
    module_path = str(relative_path.with_suffix(''))
    
    # 替换所有路径分隔符为点号
    module_path = module_path.replace("\\", ".").replace("/", ".")
    
    # 添加父级包前缀
    return f"tasks.{module_path}"

def _find_all_task_modules(base_dir: Path) -> List[str]:
    """递归查找所有任务模块路径"""
    module_paths = []
    
    for py_file in base_dir.rglob("*.py"):
        # 排除__init__.py和core.py
        if py_file.name in ("__init__.py", "core.py"):
            continue
        
        # 转换为合法模块路径
        module_path = _normalize_module_path(py_file, base_dir)
        module_paths.append(module_path)
    
    return module_paths

def _discover_tasks():
    """自动发现并导入所有任务模块"""
    tasks_dir = Path(__file__).parent
    modules = _find_all_task_modules(tasks_dir)
    
    imported = []
    for module_path in modules:
        try:
            importlib.import_module(module_path)
            imported.append(module_path)
        except Exception as e:
            # 捕获导入错误但继续执行，只记录失败模块
            print(
                f"⚠️  Failed to import task module '{module_path}': {str(e)}", 
                file=sys.stderr
            )
    
    # 调试用：显示已加载的模块
    if imported:
        print(f"✅ 自动加载任务模块: {len(imported)}个")
        for m in sorted(imported):
            print(f"    - {m}")





# 自动执行发现
_discover_tasks()

# 暴露核心功能
from .core import task_registry, register_task, get_task, execute_task

print("="*50)
print(f"已注册任务数量: {len(task_registry.all_tasks)}")
print("任务详情:")
for key, task_def in task_registry.all_tasks.items():
    print(f"\n🔹 任务Key: {key}")
    print(f"   - 描述: {task_def.description}")
    print(f"   - 函数名: {task_def.func.__name__}")
    print(f"   - 模块路径: {task_def.func.__module__}")
    
    # 打印参数信息
    if task_def.param_model:
        print("   - 参数模型:")
        for name, field in task_def.param_model.model_fields.items():
            print(f"     {name}: {field.annotation.__name__ if hasattr(field.annotation, '__name__') else field.annotation}")
    else:
        print("   - 无参数模型")
print("="*50)

__all__ = ['task_registry', 'register_task', 'get_task', 'execute_task']