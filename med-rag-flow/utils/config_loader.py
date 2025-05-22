from pathlib import Path
from datetime import timedelta
import yaml


class ConfigLoader:
    """配置加载与验证器"""
    def __init__(self, config_path: str = "../config/task/image_table_process.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_and_validate()
        self.base_dir = Path(config_path).parent.resolve()

    def _load_and_validate(self) -> dict:
        """加载并验证配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            if not all(key in config for key in ("global", "tasks")):
                raise ValueError("配置文件缺少必要字段(global/tasks)")
                
            return self._convert_types(config)

        except FileNotFoundError:
            raise
        except yaml.YAMLError as e:
            raise
        except Exception as e:
            raise

    def _convert_types(self, config: dict) -> dict:
        """递归进行类型转换"""
        if isinstance(config, dict):
            return {k: self._convert_types(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._convert_types(item) for item in config]
        elif isinstance(config, str):
            config = config.strip()
            if config.lower() in ('true', 'yes'):
                return True
            if config.lower() in ('false', 'no'):
                return False
            try:
                return int(config)
            except ValueError:
                try:
                    return float(config)
                except ValueError:
                    try:
                        return timedelta(seconds=int(config))
                    except ValueError:
                        return config
        return config