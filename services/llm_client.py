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
    last_user_request_time = 0.0
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
        self._redis_cache = None
        self._init_redis()
        self._init_client()
        self._initialized = True

    def _init_redis(self):
        """初始化 Redis 缓存连接"""
        import os
        redis_url = os.environ.get('REDIS_URL') or 'redis://127.0.0.1:6379/0'
        try:
            import redis
            self._redis_cache = redis.from_url(redis_url, socket_timeout=1)
            self._redis_cache.ping()
            print(f"[OK] LLM 接口缓存启用: {redis_url}")
        except Exception:
            self._redis_cache = None

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
            self._model_name = "glm-4.5-flash"
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
            print("[!] LLM 客户端不可用")
            return None

        # 尝试从 Redis 缓存中获取响应
        cache_key = None
        if self._redis_cache:
            try:
                import hashlib
                import json
                serialized = json.dumps({"m": messages, "t": temperature, "max": max_tokens}, sort_keys=True)
                cache_key = f"llm_cache:{hashlib.md5(serialized.encode('utf-8')).hexdigest()}"
                cached_res = self._redis_cache.get(cache_key)
                if cached_res:
                    return cached_res.decode('utf-8')
            except Exception:
                pass

        import threading
        import time

        is_worker = threading.current_thread().name.startswith('worker-')
        if not is_worker:
            SharedLLMClient.last_user_request_time = time.time()
        else:
            # Worker thread yields to active user requests
            while True:
                elapsed = time.time() - SharedLLMClient.last_user_request_time
                if elapsed < 10.0:
                    print(f"[Priority Control] Background worker {threading.current_thread().name} yielding to active user request (last request {elapsed:.1f}s ago). Sleeping 2s...")
                    time.sleep(2.0)
                else:
                    break

        import time
        max_retries = 5
        base_delay = 2  # 基础延迟秒数
        current_model = self._model_name

        for attempt in range(max_retries):
            if is_worker:
                while True:
                    elapsed = time.time() - SharedLLMClient.last_user_request_time
                    if elapsed < 10.0:
                        print(f"[Priority Control] Background worker {threading.current_thread().name} yielding to active user request (last request {elapsed:.1f}s ago). Sleeping 2s...")
                        time.sleep(2.0)
                    else:
                        break
            try:
                content = None
                if self._provider == LLMProvider.ZHIPU:
                    # Disable thinking tokens to save token budget and prevent empty response contents
                    response = self._client.chat.completions.create(
                        model=current_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        extra_body={"thinking": {"type": "disabled"}}
                    )
                    content = response.choices[0].message.content

                elif self._provider == LLMProvider.OPENAI:
                    response = self._client.chat.completions.create(
                        model=current_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    content = response.choices[0].message.content

                # 成功获取后，如果启用了 Redis，则写入缓存（缓存有效期 24 小时）
                if content and self._redis_cache and cache_key:
                    try:
                        self._redis_cache.setex(cache_key, 3600 * 24, content)
                    except Exception:
                        pass

                return content

            except Exception as e:
                err_str = str(e)
                # 判断是否是限流或速率限制错误 (如 429, 1305, rate limit, 访问量过大, 频率限制, Too Many Requests)
                is_rate_limit = (
                    "429" in err_str or
                    "1305" in err_str or
                    "rate limit" in err_str.lower() or
                    "访问量过大" in err_str or
                    "频率" in err_str or
                    "Too Many Requests" in err_str or
                    "APIReachLimitError" in type(e).__name__ or
                    "rate_limit" in type(e).__name__.lower()
                )

                if is_rate_limit and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    # 自动将 Zhipu 降级为 glm-4.5-flash
                    if self._provider == LLMProvider.ZHIPU and current_model != "glm-4.5-flash":
                        print(f"LLM API 触发限流且访问量过大，将模型从 {current_model} 降级为 glm-4.5-flash")
                        current_model = "glm-4.5-flash"
                        self._model_name = "glm-4.5-flash"
                        delay = 0.5  # 降级为 flash 模型后快速重试
                        
                    print(f"LLM API 触发限流 (429/1305/访问过大)，将在 {delay} 秒后重试 (使用模型: {current_model}, 尝试 {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                    continue
                else:
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

    def generate_image(self, prompt: str) -> Optional[str]:
        """
        根据提示词生成图像
        
        Args:
            prompt: 图像生成提示词
            
        Returns:
            生成的图像 URL，或 None（失败时）
        """
        if not self.is_available():
            print("⚠️  LLM 客户端不可用，无法生成图像")
            return None
            
        import threading
        import time

        is_worker = threading.current_thread().name.startswith('worker-')
        if not is_worker:
            SharedLLMClient.last_user_request_time = time.time()
        else:
            while True:
                elapsed = time.time() - SharedLLMClient.last_user_request_time
                if elapsed < 10.0:
                    print(f"[Priority Control] Background worker {threading.current_thread().name} yielding to active user request (last request {elapsed:.1f}s ago). Sleeping 2s...")
                    time.sleep(2.0)
                else:
                    break

        try:
            if self._provider == LLMProvider.ZHIPU:
                # 智谱 AI CogView-4 图像生成（2026年最新版，¥0.06/次）
                response = self._client.images.generations(
                    model="cogview-4",
                    prompt=prompt,
                    size="1024x1024"
                )
                if response and response.data:
                    return response.data[0].url
            elif self._provider == LLMProvider.OPENAI:
                # OpenAI DALL-E-3 图像生成
                response = self._client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    n=1
                )
                if response and response.data:
                    return response.data[0].url
        except Exception as e:
            print(f"图像生成失败: {e}")
            print(traceback.format_exc())
            return None


# 全局单例访问点
llm_client = SharedLLMClient()


def safe_zhipu_post(url, headers, json_data, timeout=30, stream=False):
    """
    统一的智谱 API POST 请求发送工具，支持 429 和 1305 高并发降级 glm-4.5-flash 与自动重试。
    """
    import requests
    import time
    import json
    import copy
    
    import threading
    import time
    
    is_worker = threading.current_thread().name.startswith('worker-')
    if not is_worker:
        SharedLLMClient.last_user_request_time = time.time()
    else:
        while True:
            elapsed = time.time() - SharedLLMClient.last_user_request_time
            if elapsed < 10.0:
                print(f"[Priority Control] Background worker {threading.current_thread().name} yielding to active user request (last request {elapsed:.1f}s ago). Sleeping 2s...")
                time.sleep(2.0)
            else:
                break

    data_copy = copy.deepcopy(json_data)
    current_model = data_copy.get("model", "glm-4.5-flash")
    max_retries = 5
    base_delay = 2
    
    for attempt in range(max_retries):
        if is_worker:
            while True:
                elapsed = time.time() - SharedLLMClient.last_user_request_time
                if elapsed < 10.0:
                    print(f"[Priority Control] Background worker {threading.current_thread().name} yielding to active user request (last request {elapsed:.1f}s ago). Sleeping 2s...")
                    time.sleep(2.0)
                else:
                    break
        try:
            data_copy["model"] = current_model
            # Disable thinking tokens for direct HTTP POST requests
            if "thinking" not in data_copy:
                data_copy["thinking"] = {"type": "disabled"}
            response = requests.post(
                url,
                headers=headers,
                json=data_copy,
                timeout=timeout,
                stream=stream
            )
            
            # 判断是否是限流或错误状态码
            if response.status_code == 429:
                raise requests.exceptions.HTTPError("HTTP 429 Too Many Requests", response=response)
            
            # 检查非流式响应体是否包含 1305 访问量过大错误
            if not stream:
                try:
                    res_json = response.json()
                    if isinstance(res_json, dict):
                        err_code = res_json.get("error", {}).get("code") or res_json.get("code")
                        err_msg = res_json.get("error", {}).get("message") or res_json.get("message")
                        if str(err_code) == "1305":
                            raise requests.exceptions.HTTPError(f"Zhipu Error 1305: {err_msg}", response=response)
                except Exception:
                    pass
            else:
                # 流式请求如果返回错误状态码，也尝试解析 1305
                if response.status_code != 200:
                    try:
                        res_json = response.json()
                        if isinstance(res_json, dict):
                            err_code = res_json.get("error", {}).get("code") or res_json.get("code")
                            if str(err_code) == "1305":
                                raise requests.exceptions.HTTPError(f"Zhipu Error 1305: {res_json}", response=response)
                    except Exception:
                        pass
                    response.raise_for_status()
            
            return response
            
        except Exception as e:
            err_str = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    err_str += " " + e.response.text
                except Exception:
                    pass
            
            is_rate_limit = (
                "429" in err_str or
                "1305" in err_str or
                "rate limit" in err_str.lower() or
                "访问量过大" in err_str or
                "频率" in err_str or
                "Too Many Requests" in err_str or
                "APIReachLimitError" in type(e).__name__ or
                "rate_limit" in type(e).__name__.lower()
            )
            
            if is_rate_limit and attempt < max_retries - 1:
                if current_model != "glm-4.5-flash":
                    print(f"[safe_zhipu_post] 触发限流，模型从 {current_model} 降级为 glm-4.5-flash")
                    current_model = "glm-4.5-flash"
                    # 更新 SharedLLMClient 的全局默认模型
                    llm_client._model_name = "glm-4.5-flash"
                    delay = 0.5
                else:
                    delay = base_delay * (2 ** attempt)
                    print(f"[safe_zhipu_post] 触发限流，将在 {delay} 秒后重试 {current_model} (尝试 {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                continue
            else:
                if attempt >= max_retries - 1:
                    print(f"[safe_zhipu_post] 达到最大重试次数，最后使用的模型是: {current_model}")
                if hasattr(e, 'response') and e.response is not None:
                    return e.response
                raise e
