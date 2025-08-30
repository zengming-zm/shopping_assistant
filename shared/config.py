import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def reload(self):
        self._config = self._load_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    @property
    def llm_router(self) -> Dict[str, Any]:
        return self.get('llm_router', {})
    
    @property
    def reranker(self) -> str:
        return self.get('reranker', 'local_bge')
    
    @property
    def vector_store(self) -> str:
        return self.get('vector_store', 'qdrant')
    
    @property
    def embeddings_model(self) -> str:
        return self.get('embeddings_model', 'all-MiniLM-L6-v2')
    
    @property
    def crawler(self) -> Dict[str, Any]:
        return self.get('crawler', {})
    
    @property
    def rag(self) -> Dict[str, Any]:
        return self.get('rag', {})
    
    @property
    def demo_apis(self) -> Dict[str, Any]:
        return self.get('demo_apis', {})
    
    @property
    def redis(self) -> Dict[str, Any]:
        return self.get('redis', {})


class EnvConfig:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')
    JINA_API_KEY = os.getenv('JINA_API_KEY')
    
    EASYPOST_TEST_API_KEY = os.getenv('EASYPOST_TEST_API_KEY')
    
    LANGFUSE_PUBLIC_KEY = os.getenv('LANGFUSE_PUBLIC_KEY')
    LANGFUSE_SECRET_KEY = os.getenv('LANGFUSE_SECRET_KEY')
    LANGFUSE_HOST = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')
    
    QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    DEMO_MODE = os.getenv('DEMO_MODE', 'true').lower() == 'true'
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'


config = Config()
env_config = EnvConfig()