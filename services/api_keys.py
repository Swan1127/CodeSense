"""
API 密钥管理服务
统一管理 ZHIPU_API_KEY 和 OPENAI_API_KEY
"""
from typing import Optional
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class APIKeyManager:
    """API 密钥管理器单例"""
    _instance: Optional['APIKeyManager'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._zhipu_key: str = os.environ.get('ZHIPU_API_KEY', '')
        self._openai_key: str = os.environ.get('OPENAI_API_KEY', '')
        self._initialized = True

    @property
    def zhipu_key(self) -> str:
        """获取智谱 AI API 密钥"""
        return self._zhipu_key

    @property
    def openai_key(self) -> str:
        """获取 OpenAI API 密钥"""
        return self._openai_key

    @property
    def has_zhipu(self) -> bool:
        """是否有智谱 AI 密钥"""
        return bool(self._zhipu_key)

    @property
    def has_openai(self) -> bool:
        """是否有 OpenAI 密钥"""
        return bool(self._openai_key)

    @property
    def has_any_key(self) -> bool:
        """是否有任意一个 API 密钥"""
        return self.has_zhipu or self.has_openai

    def get_key(self, provider: str = 'zhipu') -> str:
        """
        获取指定 provider 的 API 密钥

        Args:
            provider: 'zhipu' 或 'openai'

        Returns:
            API 密钥字符串，无密钥时返回空字符串
        """
        if provider == 'zhipu':
            return self._zhipu_key
        elif provider == 'openai':
            return self._openai_key
        return ''

    def get_provider(self) -> str:
        """
        获取可用的 API provider

        Returns:
            'zhipu', 'openai', 或 '' (无可用 provider)
        """
        if self.has_zhipu:
            return 'zhipu'
        elif self.has_openai:
            return 'openai'
        return ''


# 全局单例访问点
api_keys = APIKeyManager()
