import os
import hashlib
import logging
from typing import List, Dict, Optional
from langchain.schema import Document
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStoreManager:
    """向量存储管理器，支持内容感知存储和增量更新"""
    
    def __init__(self, 
                 config: Dict,
                 docs: List[Document],
                 auto_init: bool = True):
        """
        参数说明：
        config: 配置字典，结构示例：
            {
                "models": {
                    "name": "nomic-embed-text",
                    "base_url": "http://localhost:11434"
                },
                "vector_store": {
                    "base_path": "./storage",
                    "naming_template": "vec_{model_hash}_{doc_hash}"
                }
            }
        docs: 预处理完成的文档列表
        auto_init: 是否自动初始化存储
        """
        # 配置验证
        if not self._validate_config(config):
            raise ValueError("Invalid configuration structure")
            
        self.config = config
        self._original_docs = docs.copy()
        self.docs = docs
        self.vectorstore: Optional[FAISS] = None
        self.vector_store_path = self._generate_store_path()
        
        if auto_init:
            self.initialize_store()

    def _validate_config(self, config: Dict) -> bool:
        """配置结构验证"""
        required_keys = {
            "models": ["name", "base_url"],
            "vector_store": ["base_path", "naming_template"]
        }
        for section, keys in required_keys.items():
            if section not in config:
                logger.error(f"Missing config section: {section}")
                return False
            for key in keys:
                if key not in config[section]:
                    logger.error(f"Missing key: {section}.{key}")
                    return False
        return True

    def initialize_store(self):
        """智能初始化流程"""
        if self._try_load_existing_store():
            logger.info(f"成功加载已有存储: {self.vector_store_path}")
        else:
            logger.info("未找到现有存储，创建新存储")
            self.create_vector_store(self.docs)

    def compute_content_hash(self) -> str:
        """基于文档内容生成唯一哈希"""
        content_hash = hashlib.md5()
        
        # 排序保证顺序无关
        for doc in sorted(self.docs, key=lambda x: x.page_content):
            content_hash.update(doc.page_content.encode('utf-8'))
            # 包含元数据特征（可选）
            content_hash.update(str(doc.metadata).encode('utf-8'))
        
        return content_hash.hexdigest()[:8]

    def _generate_store_path(self) -> str:
        """生成存储路径（包含内容哈希）"""
        model_hash = hashlib.md5(
            self.config["models"]["name"].encode()
        ).hexdigest()[:6]  # 6位模型哈希
        
        content_hash = self.compute_content_hash()
        self.vector_store_path_name = self.config["vector_store"]["naming_template"].format(
                model_hash=model_hash,
                doc_hash=content_hash[:6]
        )
        return os.path.join(
            self.config["vector_store"]["base_path"],
            self.config["vector_store"]["naming_template"].format(
                model_hash=model_hash,
                doc_hash=content_hash[:6]
            )
        )

    def create_vector_store(self, docs: List[Document]):
        """创建/覆盖向量存储"""
        logger.info(f"重建向量存储，处理文档数: {len(docs)}")
        self.vectorstore = FAISS.from_documents(
            docs,
            self.get_embeddings()
        )
        self._save_vector_store()

    def update_documents(self, new_docs: List[Document]):
        """全量更新文档（使用新文档完全替换现有存储）"""
        if not self.vectorstore:
            logger.warning("存储未初始化，执行全量创建")
            self.create_vector_store(new_docs)
            return

        # 替换当前文档集合
        self.docs = new_docs.copy()
        
        # 重新生成存储路径（可选，根据需求决定是否保留路径）
        # 如果要保持路径不变，可注释下面这行
        self.vector_store_path = self._generate_store_path()

        # 强制重建存储
        logger.info("开始全量更新存储")
        self.create_vector_store(self.docs)
        
        logger.info(f"存储更新完成，当前文档数: {len(self.docs)}")

    def _save_vector_store(self):
        """安全保存存储"""
        if not self.vectorstore:
            raise RuntimeError("向量存储未初始化")
            
        os.makedirs(os.path.dirname(self.vector_store_path), exist_ok=True)
        logger.info(f"保存存储到: {self.vector_store_path}")
        try:
            self.vectorstore.save_local(self.vector_store_path)
        except Exception as e:
            logger.error(f"存储保存失败: {str(e)}")
            raise

    def _try_load_existing_store(self) -> bool:
        """尝试加载存储"""
        if os.path.exists(self.vector_store_path):
            try:
                logger.info(f"尝试加载存储: {self.vector_store_path}")
                self.vectorstore = FAISS.load_local(
                    self.vector_store_path,
                    self.get_embeddings(),
                    allow_dangerous_deserialization=True
                )
                return True
            except Exception as e:
                logger.error(f"存储加载失败: {str(e)}")
                return False
        return False

    def get_embeddings(self) -> OllamaEmbeddings:
        """获取嵌入模型实例"""
        return OllamaEmbeddings(
            model=self.config["models"]["name"],
            base_url=self.config["models"]["base_url"]
        )

    def get_store_info(self) -> Dict:
        """获取存储元信息"""
        return {
            "model": self.config["models"]["name"],
            "doc_count": len(self.docs),
            "content_hash": self.compute_content_hash(),
            "store_path": self.vector_store_path,
            "versions": self.list_versions()
        }

    def list_versions(self) -> List[str]:
        """列出所有存储版本"""
        base_dir = self.config["vector_store"]["base_path"]
        pattern = os.path.basename(self.vector_store_path).split('_')[0] + '_*'
        return [d for d in os.listdir(base_dir) if os.path.isdir(d) and d.startswith(pattern)]

    @property
    def is_ready(self) -> bool:
        """就绪状态检查"""
        return self.vectorstore is not None

# 使用示例
if __name__ == "__main__":
    config = {
        "models": {
            "name": "linux6200/bge-reranker-v2-m3:latest",
            "base_url": "http://localhost:11434"
        },
        "vector_store": {
            "base_path": "../../data/vectorstorage",
            "naming_template": "vec_{model_hash}_{doc_hash}"
        }
    }

    # 初始文档集
    docs = [
        Document(page_content="设备维护指南", metadata={"section": "intro"}),
        Document(page_content="安全操作规程", metadata={"section": "safety"})
    ]

    # 初始化管理器
    manager = VectorStoreManager(config, docs)
    
    # 获取元信息
    print("初始存储信息:", manager.get_store_info())

    # 增量更新
    # new_docs = [
    #     Document(page_content="故障排除手册", metadata={"section": "troubleshooting"})
    # ]
    # manager.update_documents(new_docs)
    
    # # 更新后信息
    # print("更新后存储信息:", manager.get_store_info())