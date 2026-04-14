"""
共享 LLM 客户端服务
单例模式，避免多重初始化浪费资源
"""
from typing import Optional, Tuple, Dict, Any
from enum import Enum
import traceback

# 导入 API 密钥管理器
from services.api_keys import api_keys


class LLMProvider(Enum):
    """支持的 LLM Provider"""
    ZHIPU = "zhipu"
    OPENAI = "openai"


class SharedLLMClient:
    """
    共享 LLM 客户端单例

    使用方式:
        llm_client = SharedLLMClient()
        if llm_client.is_available():
            score, feedback = llm_client.evaluate_code(code, title)
    """
    _instance: Optional['SharedLLMClient'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._client = None
        self._provider: LLMProvider = None
        self._model_name: str = ""
        self._available: bool = False
        self._init_client()
        self._initialized = True

    def _init_client(self):
        """初始化 LLM 客户端"""
        if not api_keys.has_any_key:
            print("⚠️  没有可用的 API 密钥，LLM 客户端不可用")
            return

        # 确定使用的 provider
        if api_keys.has_zhipu:
            self._provider = LLMProvider.ZHIPU
            self._init_zhipu_client()
        elif api_keys.has_openai:
            self._provider = LLMProvider.OPENAI
            self._init_openai_client()
        else:
            print("⚠️  没有可用的 API 密钥")
            self._available = False

    def _init_zhipu_client(self):
        """初始化智谱 AI 客户端"""
        try:
            from zhipuai import ZhipuAI

            api_key = api_keys.zhipu_key
            if not api_key:
                print("⚠️  智谱 AI API 密钥为空")
                self._available = False
                return

            self._client = ZhipuAI(api_key=api_key)
            self._model_name = "glm-4-flash"
            self._available = True
            print("✅ 共享智谱 AI 客户端初始化成功")
        except ImportError:
            print("⚠️  未安装 zhipuai 库")
            self._available = False
        except Exception as e:
            print(f"⚠️  智谱 AI 客户端初始化失败: {e}")
            self._available = False

    def _init_openai_client(self):
        """初始化 OpenAI 客户端"""
        try:
            from openai import OpenAI

            api_key = api_keys.openai_key
            if not api_key:
                print("⚠️  OpenAI API 密钥为空")
                self._available = False
                return

            self._client = OpenAI(api_key=api_key)
            self._model_name = "gpt-4-turbo"
            self._available = True
            print("✅ 共享 OpenAI 客户端初始化成功")
        except ImportError:
            print("⚠️  未安装 openai 库")
            self._available = False
        except Exception as e:
            print(f"⚠️  OpenAI 客户端初始化失败: {e}")
            self._available = False

    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return self._available and self._client is not None

    @property
    def provider(self) -> Optional[str]:
        """获取当前 provider"""
        return self._provider.value if self._provider else None

    @property
    def model_name(self) -> str:
        """获取模型名称"""
        return self._model_name

    def chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
        """
        发送对话请求

        Args:
            messages: 消息列表 [{"role": "system"/"user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            响应内容，或 None（失败时）
        """
        if not self.is_available():
            print("⚠️  LLM 客户端不可用")
            return None

        try:
            if self._provider == LLMProvider.ZHIPU:
                response = self._client.chat.completions.create(
                    model=self._model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content

            elif self._provider == LLMProvider.OPENAI:
                response = self._client.chat.completions.create(
                    model=self._model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content

        except Exception as e:
            print(f"LLM API 调用失败: {e}")
            print(traceback.format_exc())
            return None

    def evaluate_code(self, code: str, assignment_title: str = None) -> Tuple[int, str]:
        """
        评估代码

        Args:
            code: 代码内容
            assignment_title: 题目标题

        Returns:
            (score: 0-5, feedback: str)
        """
        if not self.is_available():
            return 3, "LLM 服务不可用，使用默认评分"

        system_prompt = """你是一名经验丰富的C++编程教师，评估学生代码质量。
评分标准: 1-5分，5分最高。请先给出分数，再用"分析："分隔详细反馈。

格式: "分数：X\n分析：..."""


        user_prompt = f"题目：{assignment_title or '未指定'}\n\n代码：\n{code}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.chat(messages, temperature=0.2)
        if not response:
            return 3, "LLM 响应失败，使用默认评分"

        # 解析分数
        import re
        score_match = re.search(r'分数[：:]\s*(\d+)', response)
        if score_match:
            score = int(score_match.group(1))
            score = max(0, min(5, score))
        else:
            score = 3  # 默认中等评分

        # 提取反馈
        if "分析：" in response:
            feedback = response.split("分析：", 1)[1].strip()
        else:
            feedback = response

        return score, feedback


# 全局单例访问点
llm_client = SharedLLMClient()
