from typing import Dict, List, Generator
import os
import json
import requests
from dotenv import load_dotenv
import re

# 加载环境变量
load_dotenv()

# 导入统一的 API 密钥管理器
from services.api_keys import api_keys


class AIEvaluator:
    def __init__(self, api_key: str = None):
        """初始化智谱AI评估器"""
        # 优先使用传入的api_key，如果没有则使用统一的 API 密钥管理器
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = api_keys.get_key('zhipu')
        
    def evaluate_code(self, code: str, assignment_title: str) -> Dict:
        """使用智谱大模型评估代码"""
        prompt = f"""请分析以下代码的编程能力水平，从以下维度进行评估：
1. 算法能力：评估算法设计、逻辑思维、问题求解能力
2. 代码风格：评估代码可读性、命名规范、注释质量
3. 功能实现：评估功能完整性、正确性、健壮性
4. 效率优化：评估时间复杂度、空间复杂度、资源利用
5. 代码可读性：评估代码的易读性和可维护性

作业标题：{assignment_title}
代码：
{code}

请以 JSON 格式返回评估结果，包含以下字段：
- algorithm_score: 算法能力得分(0-100)
- style_score: 代码风格得分(0-100)
- functionality_score: 功能实现得分(0-100)
- efficiency_score: 效率优化得分(0-100)
- readability_score: 代码可读性得分(0-100)
- feedback: 详细的评估反馈和建议。具体要求：
    1. 使用标准的 **Markdown** 格式。
    2. 使用 `###` 标题进行分段（例如：### 算法逻辑、### 改进建议）。
    3. 使用有序列表 `1. 2. 3.` 或无序列表 `-`。
    4. 适当使用 **加粗** 强调关键点。
    5. 确保内容分段清晰，易于阅读。
"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": "你是一个专业的代码评估专家，擅长分析代码质量和编程能力。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                result_content = result["choices"][0]["message"]["content"]
                result_json = json.loads(result_content)
                return result_json
            else:
                print(f"智谱API请求失败: {response.status_code} - {response.text}")
                return {
                    "algorithm_score": 60, "style_score": 60,
                    "functionality_score": 60, "efficiency_score": 60,
                    "readability_score": 60, "feedback": "评估过程中出现错误，请稍后重试。"
                }
        except Exception as e:
            print(f"AI评估出错: {str(e)}")
            return {
                "algorithm_score": 60, "style_score": 60,
                "functionality_score": 60, "efficiency_score": 60,
                "readability_score": 60, "feedback": "评估过程中出现错误，请稍后重试。"
            }

    def format_assignment_text(self, raw_text: str) -> Generator[str, None, None]:
        """
        将原始作业文本通过 LLM 解析或根据简短指令生成完整作业，流式返回 JSON 字符串。
        支持两种模式：
        1. 格式化模式：输入为详细的作业原始文本，AI 提取并格式化
        2. 创造模式：输入为简短的指令/描述，AI 自主设计一道具体、完整的编程题
        JSON 包含字段：suggested_id (int)、title (str)、description (Markdown str)、test_cases (array)。
        调用方收集所有 chunk 拼接后再解析 JSON。
        """
        prompt = f"""你是一位资深计算机科学教授和出题专家。你需要根据用户提供的文本，以**严格**的 JSON 格式输出一道完整的编程作业题。

**核心规则**：
- 如果用户输入是**简短的指令或描述**（例如"留一个动态规划的作业"、"设计一道链表题"、"C语言考察指针"），你必须**自主创造一道具体、详细、可执行的编程题目**。绝对不能输出占位符（如"输入样例1"、"具体输入格式根据题目要求设计"）。你必须给出一道真实的、有明确输入输出的题目。
- 如果用户输入是**较长的完整作业文本**，则提取关键信息，格式化为结构化的 JSON。

**输出格式**（严格 JSON，不得在 JSON 外附加任何文字）：
{{
  "suggested_id": <建议的整数作业ID，范围101-999>,
  "title": "<简洁的中文作业标题，如：最长公共子序列、0-1背包问题>",
  "description": "<完整的 Markdown 格式作业描述，必须包含以下章节：\\n### 作业描述\\n（具体的题目背景和要求，不少于100字）\\n\\n### 输入格式\\n（明确每一行输入什么，数据范围是什么）\\n\\n### 输出格式\\n（明确输出什么）\\n\\n### 输入样例\\n```\\n（真实的样例数据）\\n```\\n\\n### 输出样例\\n```\\n（对应的真实输出）\\n```>",
  "test_cases": [
    {{"input": "<真实的测试输入数据>", "output": "<对应的正确输出>", "is_public": true}},
    {{"input": "<真实的测试输入数据>", "output": "<对应的正确输出>", "is_public": false}}
  ]
}}

**test_cases 要求**：
- 生成4-6个测试用例，至少2个公开（is_public=true）、2个隐藏（is_public=false）
- 每个测试用例的 input 和 output 必须是**真实的、可验证的数据**，不能是占位符
- 隐藏用例应包含边界情况（如最小值、最大值、特殊情况）

**示例**——当用户输入"留一个动态规划的C语言作业"时，你应该输出类似：
{{
  "suggested_id": 305,
  "title": "最长递增子序列",
  "description": "### 作业描述\\n给定一个整数序列，找到其中最长的严格递增子序列的长度。\\n\\n子序列是指从原序列中删除若干（可以为零）个元素后，剩余元素保持原有先后顺序所组成的序列。\\n\\n请使用动态规划方法求解此问题。\\n\\n### 输入格式\\n第一行包含一个正整数 n（1 ≤ n ≤ 1000），表示序列的长度。\\n第二行包含 n 个整数 a₁, a₂, ..., aₙ（-10000 ≤ aᵢ ≤ 10000），表示序列中的各元素，用空格分隔。\\n\\n### 输出格式\\n输出一个整数，表示最长严格递增子序列的长度。\\n\\n### 输入样例\\n```\\n8\\n10 9 2 5 3 7 101 18\\n```\\n\\n### 输出样例\\n```\\n4\\n```\\n\\n### 提示\\n最长递增子序列为 [2, 3, 7, 101] 或 [2, 5, 7, 101] 等，长度为 4。",
  "test_cases": [
    {{"input": "8\\n10 9 2 5 3 7 101 18", "output": "4", "is_public": true}},
    {{"input": "5\\n1 2 3 4 5", "output": "5", "is_public": true}},
    {{"input": "5\\n5 4 3 2 1", "output": "1", "is_public": false}},
    {{"input": "1\\n42", "output": "1", "is_public": false}},
    {{"input": "6\\n3 1 4 1 5 9", "output": "4", "is_public": false}}
  ]
}}

现在请处理以下用户输入：
\"\"\"
{raw_text}
\"\"\""""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "glm-4-flash",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是一个专业的编程作业出题与格式化助手。"
                            "当用户输入简短的指令或描述时，你必须自主设计一道具体的、有明确输入输出的编程题目，包含真实的测试数据。"
                            "当用户输入较长的原始文本时，你需要将其格式化提取为结构化作业。"
                            "你必须且只能输出合法的 JSON，不得在 JSON 前后添加任何解释文字或 Markdown 代码块标记。"
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 3000,
                "stream": True
            }
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=90,
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data:'):
                        json_str = decoded_line[len('data:'):].strip()
                        if json_str and json_str != '[DONE]':
                            try:
                                chunk = json.loads(json_str)
                                if chunk.get('choices'):
                                    content = chunk['choices'][0]['delta'].get('content', '')
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                print(f"Skipping non-JSON SSE line: {json_str}")
                                continue
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            yield json.dumps({"error": f"API请求失败: {str(e)}"})
        except Exception as e:
            print(f"An exception occurred during streaming: {e}")
            yield json.dumps({"error": f"发生错误: {str(e)}"})

    def analyze_ability_trend(self, submissions: List[Dict]) -> Dict:
        """分析编程能力发展趋势"""
        if not submissions:
            return {
                "trend": "暂无数据",
                "improvement": "请提交更多代码以获取分析",
                "suggestions": []
            }
            
        prompt = f"""请分析以下代码提交记录，评估编程能力的发展趋势和改进建议：

提交记录：
{json.dumps(submissions, ensure_ascii=False, indent=2)}

重要提示：请严格按照JSON格式返回分析结果，不要添加任何其他文本或格式标记。

必须返回如下格式的JSON：
{{
  "trend": "能力发展趋势的详细描述",
  "improvement": "具体的改进建议",
  "suggestions": [
    "具体改进措施1",
    "具体改进措施2",
    "具体改进措施3"
  ]
}}

请确保返回的是纯JSON格式，不要包含markdown代码块标记或其他格式。
"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": "你是一个专业的编程教育专家，擅长分析学习趋势和提供改进建议。请严格按照JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 完整API响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                if "choices" not in result or len(result["choices"]) == 0:
                    raise Exception("API响应格式错误：缺少choices字段")
                if "message" not in result["choices"][0]:
                    raise Exception("API响应格式错误：缺少message字段")
                message = result["choices"][0]["message"]
                result_content = message.get("content", "") or message.get("reasoning_content", "")
                print(f"📄 API返回内容长度: {len(result_content) if result_content else 0}")
                print(f"📄 API返回内容前200字符: {result_content[:200] if result_content else '(空内容)'}")
                if not result_content or not result_content.strip():
                    raise Exception("API返回空内容")
                if result["choices"][0].get("finish_reason") == "length":
                    reasoning_content = message.get("reasoning_content", "")
                    if reasoning_content:
                        return self._extract_from_natural_language(reasoning_content)
                content_trimmed = result_content.strip()
                if not content_trimmed.startswith('{'):
                    return self._extract_from_natural_language(content_trimmed)
                cleaned_content = content_trimmed
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]
                elif cleaned_content.startswith('```'):
                    lines = cleaned_content.split('\n')
                    if len(lines) > 1:
                        cleaned_content = '\n'.join(lines[1:])
                        if cleaned_content.endswith('```'):
                            cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                try:
                    result_dict = json.loads(cleaned_content)
                    if 'suggestions' in result_dict and isinstance(result_dict['suggestions'], list):
                        result_dict['suggestions'] = [self._clean_suggestion(s) for s in result_dict['suggestions']]
                    return result_dict
                except Exception as e:
                    json_match = re.search(r'({.*})', cleaned_content.replace('\n', ''), re.DOTALL)
                    if json_match:
                        try:
                            result_dict = json.loads(json_match.group(1))
                            if 'suggestions' in result_dict and isinstance(result_dict['suggestions'], list):
                                result_dict['suggestions'] = [self._clean_suggestion(s) for s in result_dict['suggestions']]
                            return result_dict
                        except Exception:
                            pass
                    return {
                        "trend": f"分析过程中出现解析错误: {str(e)[:100]}",
                        "improvement": "请检查API返回格式或稍后重试",
                        "suggestions": ["检查网络连接", "确认API密钥有效", "稍后重试"]
                    }
            else:
                print(f"智谱API请求失败: {response.status_code} - {response.text}")
                return {"trend": "分析过程中出现错误", "improvement": "请稍后重试", "suggestions": []}
        except Exception as e:
            print(f"能力趋势分析出错: {str(e)}")
            return {"trend": "分析过程中出现错误", "improvement": "请稍后重试", "suggestions": []}

    def _clean_suggestion(self, suggestion: str) -> str:
        """清理建议文本中的格式标记"""
        if not suggestion:
            return ""
        cleaned = re.sub(r'\{+[a-zA-Z0-9_]+\}+', '', suggestion)
        cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
        
    def _extract_from_natural_language(self, content: str) -> Dict:
        """从自然语言响应中提取结构化信息"""
        try:
            trend_text = "从提交记录分析，编程能力呈现良好发展趋势"
            trend_patterns = [
                r'编程能力[呈现展示表明]*([^。]{20,80})',
                r'([^。]{10,80}趋势[^。]{5,40})',
                r'从[^。]{5,15}来看[^。]*([^。]{20,80})',
                r'学生[^。]*能力[^。]*([^。]{15,60})'
            ]
            for pattern in trend_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    clean_matches = [m.strip() for m in matches[:2] if len(m.strip()) > 10]
                    if clean_matches:
                        trend_text = "从提交记录分析，" + "，".join(clean_matches)
                        break

            improvement_text = "建议继续加强基础算法练习，提高代码质量和规范性"
            improvement_patterns = [
                r'### 改进建议\s*([^#]{100,300})',
                r'改进建议[：:]\s*([^。]{50,150})',
                r'建议([^。]{30,100})',
                r'需要([^。]{20,80})'
            ]
            for pattern in improvement_patterns:
                matches = re.findall(pattern, content, re.DOTALL)
                if matches:
                    match_text = re.sub(r'\s+', ' ', matches[0].strip())
                    if len(match_text) > 20:
                        improvement_text = match_text[:200] + ("..." if len(match_text) > 200 else "")
                        break

            suggestions = []
            numbered_patterns = [
                r'\d+\.\s*\*\*([^*]+)\*\*[：:]?\s*([^。\n]{15,100})',
                r'\d+\.\s*([^。\n：:]{20,120})[。\n]',
            ]
            for pattern in numbered_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    if isinstance(matches[0], tuple):
                        suggestions = [f"{m[0]}：{m[1]}" if len(m) > 1 and m[1] else m[0] for m in matches[:6]]
                    else:
                        suggestions = list(matches[:6])
                    suggestions = [s.strip() for s in suggestions if len(s.strip()) > 15]
                    if suggestions:
                        break

            if not suggestions:
                suggestion_keywords = ['可以', '应该', '尝试', '学习', '练习', '增加', '提高', '避免']
                for line in content.split('\n'):
                    line = line.strip()
                    if (any(kw in line for kw in suggestion_keywords) and
                            20 < len(line) < 150 and not line.startswith('#')):
                        suggestions.append(line)
                        if len(suggestions) >= 6:
                            break

            if not suggestions:
                suggestions = [
                    "加强基础算法练习，重点掌握排序和查找算法的原理和实现",
                    "提高代码提交的准确性，避免重复提交和错误提交",
                    "增加代码测试覆盖率，为每个算法编写完整的测试用例",
                    "学习算法优化技巧，关注时间和空间复杂度的改进",
                    "扩展数据结构知识，学习树、图等高级数据结构"
                ]

            return {"trend": trend_text, "improvement": improvement_text, "suggestions": suggestions[:8]}

        except Exception as e:
            print(f"❌ 从自然语言中提取信息失败: {e}")
            return {
                "trend": "AI分析显示您的编程能力正在稳步提升",
                "improvement": "建议继续保持良好的编程习惯，加强基础算法练习",
                "suggestions": [
                    "多练习基础算法，特别是排序和查找算法的变种实现",
                    "注重代码规范，提高变量命名和注释的质量",
                    "增加边界条件测试，确保代码在各种输入下的健壮性",
                    "学习算法复杂度分析，理解时间和空间效率的权衡",
                    "练习代码重构，提高代码的可维护性和可读性"
                ]
            }

    def analyze_ability_trend_stream(self, submissions: List[Dict]) -> Generator[str, None, None]:
        """流式分析编程能力发展趋势，使用SSE方式实时返回分析结果"""
        if not submissions:
            yield "### 暂无提交数据\n\n请提交更多代码以获取详细分析。"
            return

        prompt = f"""请分析以下代码提交记录，详细评估学生的编程能力发展趋势。

提交记录数量：{len(submissions)}条

提交详情：
{json.dumps(submissions[:10], ensure_ascii=False, indent=2)}

请从能力发展趋势、改进建议、具体行动措施三个方面进行深入分析。
用中文输出，语言简洁专业，直接输出分析内容，不要JSON格式。
"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": "你是一个专业的编程教育专家，擅长分析学生的学习趋势和提供有针对性的改进建议。请用简洁专业的中文直接输出分析内容。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
                "stream": True
            }
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers, json=data, stream=True, timeout=(10, 120)
            )
            if response.status_code == 200:
                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:].strip()
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                if 'choices' in chunk_data and chunk_data['choices']:
                                    content = chunk_data['choices'][0].get('delta', {}).get('content', '')
                                    if content:
                                        chunk_count += 1
                                        yield content
                            except json.JSONDecodeError:
                                continue
            else:
                yield "\n\n【能力发展趋势】\n从您的提交记录来看，编程能力呈现稳步提升的趋势。\n\n"
                yield "【改进建议】\n1. 加强算法基础\n2. 提高代码规范性\n3. 增加测试用例\n"
        except Exception as e:
            print(f"流式分析出错: {str(e)}")
            yield f"\n\n分析过程中出现错误: {str(e)}\n请稍后重试。"

    def detect_code_knowledge_points(self, code: str, assignment_title: str) -> List[Dict]:
        """使用AI自动检测代码涉及的C语言知识点"""
        prompt = f"""请分析以下C语言代码，识别其中涉及的主要知识点。

作业标题：{assignment_title}

代码：
```c
{code[:1000]}
```

请从以下知识点中选择最相关的3-5个：
basic_syntax, pointer, function, array, string, struct, file_io,
dynamic_memory, linked_list, tree, sorting, searching, recursion

对于每个知识点，评估 weight(0.5-2.0) 和 difficulty(0.5-2.0)。

请以JSON格式返回：
[
  {{"knowledge_point": "pointer", "weight": 1.5, "difficulty": 1.2}}
]
"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": "你是一个C语言专家，擅长识别代码中的知识点。请严格按照JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers, json=data, timeout=15
            )
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                return json.loads(content.strip())
            return []
        except Exception as e:
            print(f"知识点检测失败: {str(e)}")
            return self._infer_knowledge_points_from_title(assignment_title)

    def _infer_knowledge_points_from_title(self, title: str) -> List[Dict]:
        """基于标题关键词推断知识点"""
        title_lower = title.lower()
        keyword_map = {
            'pointer': ['指针', 'pointer', '*'],
            'array': ['数组', 'array', '[]'],
            'function': ['函数', 'function'],
            'string': ['字符串', 'string', 'str'],
            'struct': ['结构体', 'struct'],
            'linked_list': ['链表', 'list', '节点'],
            'tree': ['树', 'tree', '二叉'],
            'sorting': ['排序', 'sort'],
            'searching': ['查找', '搜索', 'search'],
            'recursion': ['递归', 'recursion'],
            'dynamic_memory': ['malloc', 'free', '动态'],
            'file_io': ['文件', 'file']
        }
        knowledge_points = []
        for kp, keywords in keyword_map.items():
            if any(kw in title_lower for kw in keywords):
                knowledge_points.append({'knowledge_point': kp, 'weight': 1.0, 'difficulty': 1.0})
        if not knowledge_points:
            knowledge_points.append({'knowledge_point': 'basic_syntax', 'weight': 1.0, 'difficulty': 1.0})
        return knowledge_points

                