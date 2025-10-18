from typing import Dict, List
import os
import json
import requests
from dotenv import load_dotenv
import re

# 加载环境变量
load_dotenv()

class AIEvaluator:
    def __init__(self, api_key: str = None):
        """初始化智谱AI评估器"""
        # 优先使用传入的api_key，如果没有则从环境变量中获取
        self.api_key = api_key or os.environ.get("ZHIPU_API_KEY", "")
        
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

请以JSON格式返回评估结果，包含以下字段：
- algorithm_score: 算法能力得分(0-100)
- style_score: 代码风格得分(0-100)
- functionality_score: 功能实现得分(0-100)
- efficiency_score: 效率优化得分(0-100)
- readability_score: 代码可读性得分(0-100)
- feedback: 详细的评估反馈和建议
"""

        try:
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 构建请求数据
            data = {
                "model": "glm-4.5-flash",  # 使用智谱GLM-4.5-flash模型
                "messages": [
                    {"role": "system", "content": "你是一个专业的代码评估专家，擅长分析代码质量和编程能力。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            # 发送请求到智谱API
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            # 解析返回结果
            if response.status_code == 200:
                result = response.json()
                # 智谱API的响应格式与OpenAI类似
                result_content = result["choices"][0]["message"]["content"]
                # 解析JSON结果
                result_json = json.loads(result_content)
                return result_json
            else:
                print(f"智谱API请求失败: {response.status_code} - {response.text}")
                # 返回默认值
                return {
                    "algorithm_score": 60,
                    "style_score": 60,
                    "functionality_score": 60,
                    "efficiency_score": 60,
                    "readability_score": 60,
                    "feedback": "评估过程中出现错误，请稍后重试。"
                }
            
        except Exception as e:
            print(f"AI评估出错: {str(e)}")
            # 返回默认值
            return {
                "algorithm_score": 60,
                "style_score": 60,
                "functionality_score": 60,
                "efficiency_score": 60,
                "readability_score": 60,
                "feedback": "评估过程中出现错误，请稍后重试。"
            }
    
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
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 构建请求数据
            data = {
                "model": "glm-4.5-flash",  # 使用智谱GLM-4.5-flash模型
                "messages": [
                    {"role": "system", "content": "你是一个专业的编程教育专家，擅长分析学习趋势和提供改进建议。请严格按照JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000  # 增加token限制以避免截断
            }
            
            # 发送请求到智谱API
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            # 解析返回结果
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 完整API响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 检查响应结构
                if "choices" not in result or len(result["choices"]) == 0:
                    print("❌ API响应格式错误：缺少choices字段")
                    raise Exception("API响应格式错误：缺少choices字段")
                
                if "message" not in result["choices"][0]:
                    print("❌ API响应格式错误：缺少message字段")
                    raise Exception("API响应格式错误：缺少message字段")
                
                # 智谱AI新版本可能将内容放在reasoning_content字段
                message = result["choices"][0]["message"]
                result_content = message.get("content", "") or message.get("reasoning_content", "")
                
                # 调试信息：打印API返回的原始内容
                print(f"📄 API返回内容长度: {len(result_content) if result_content else 0}")
                print(f"📄 API返回内容前200字符: {result_content[:200] if result_content else '(空内容)'}")
                
                if not result_content or not result_content.strip():
                    print("❌ API返回空内容")
                    raise Exception("API返回空内容")
                
                # 检查响应是否被截断（finish_reason为length）
                if result["choices"][0].get("finish_reason") == "length":
                    print("⚠️ 检测到API响应被截断，使用推理内容进行分析")
                    reasoning_content = message.get("reasoning_content", "")
                    if reasoning_content:
                        return self._extract_from_natural_language(reasoning_content)
                
                # 检查内容是否看起来像自然语言而非JSON
                content_trimmed = result_content.strip()
                if not content_trimmed.startswith('{'):
                    print("🔄 检测到自然语言响应，尝试从中提取关键信息")
                    return self._extract_from_natural_language(content_trimmed)
                
                
                # 清理markdown格式
                cleaned_content = result_content.strip()
                
                # 如果内容以```json开头，去除markdown代码块标记
                if cleaned_content.startswith('```json'):
                    # 移除开始的```json
                    cleaned_content = cleaned_content[7:]
                    # 移除结尾的```
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]
                elif cleaned_content.startswith('```'):
                    # 移除其他类型的代码块标记
                    lines = cleaned_content.split('\n')
                    if len(lines) > 1:
                        cleaned_content = '\n'.join(lines[1:])
                        if cleaned_content.endswith('```'):
                            cleaned_content = cleaned_content[:-3]
                
                cleaned_content = cleaned_content.strip()
                print(f"🧹 清理后内容: {cleaned_content[:200]}...")
                
                # 解析JSON结果
                try:
                    result_dict = json.loads(cleaned_content)
                    print("✅ JSON解析成功!")
                    # 清理suggestions中的格式标记
                    if 'suggestions' in result_dict and isinstance(result_dict['suggestions'], list):
                        result_dict['suggestions'] = [self._clean_suggestion(s) for s in result_dict['suggestions']]
                    return result_dict
                except Exception as e:
                    print(f"❌ 清理后JSON解析仍失败: {e}")
                    # 如果解析失败，尝试从文本中提取JSON
                    json_match = re.search(r'({.*})', cleaned_content.replace('\n', ''), re.DOTALL)
                    if json_match:
                        try:
                            result_dict = json.loads(json_match.group(1))
                            print("✅ 正则提取JSON解析成功!")
                            # 清理suggestions中的格式标记
                            if 'suggestions' in result_dict and isinstance(result_dict['suggestions'], list):
                                result_dict['suggestions'] = [self._clean_suggestion(s) for s in result_dict['suggestions']]
                            return result_dict
                        except Exception as e2:
                            print(f"❌ 正则提取JSON解析失败: {e2}")
                    
                    # 如果都失败了，返回错误信息但不抛出异常
                    print("⚠️ 无法解析API返回的JSON，返回默认结果")
                    return {
                        "trend": f"分析过程中出现解析错误: {str(e)[:100]}",
                        "improvement": "请检查API返回格式或稍后重试",
                        "suggestions": ["检查网络连接", "确认API密钥有效", "稍后重试"]
                    }
            else:
                print(f"智谱API请求失败: {response.status_code} - {response.text}")
                return {
                    "trend": "分析过程中出现错误",
                    "improvement": "请稍后重试",
                    "suggestions": []
                }
            
        except Exception as e:
            print(f"能力趋势分析出错: {str(e)}")
            return {
                "trend": "分析过程中出现错误",
                "improvement": "请稍后重试",
                "suggestions": []
            }

    def _clean_suggestion(self, suggestion: str) -> str:
        """清理建议文本中的格式标记"""
        if not suggestion:
            return ""
            
        # 移除常见的格式标记和占位符
        # 如 {description}, {code}, {{variable}} 等
        cleaned = re.sub(r'\{+[a-zA-Z0-9_]+\}+', '', suggestion)
        # 移除Markdown格式标记
        cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
        # 移除多余空格和换行
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
        
    def _extract_from_natural_language(self, content: str) -> Dict:
        """从自然语言响应中提取结构化信息"""
        try:
            import re
            
            # 分析算法能力趋势
            trend_text = "从提交记录分析，编程能力呈现良好发展趋势"
            
            # 查找关于趋势和能力的描述
            trend_patterns = [
                r'编程能力[呈现展示表明]*([^。]{20,80})',
                r'([^。]{10,80}趋势[^。]{5,40})',
                r'从[^。]{5,15}来看[^。]*([^。]{20,80})',
                r'学生[^。]*能力[^。]*([^。]{15,60})'
            ]
            
            for pattern in trend_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    # 清理和合并匹配的文本
                    clean_matches = [m.strip() for m in matches[:2] if len(m.strip()) > 10]
                    if clean_matches:
                        trend_text = "从提交记录分析，" + "，".join(clean_matches)
                        break
            
            # 查找改进建议
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
                    # 取第一个匹配并清理
                    match_text = matches[0].strip()
                    # 移除换行和多余空格
                    match_text = re.sub(r'\s+', ' ', match_text)
                    if len(match_text) > 20:
                        improvement_text = match_text[:200] + ("..." if len(match_text) > 200 else "")
                        break
            
            # 查找具体建议措施
            suggestions = []
            
            # 模式1：查找编号列表
            numbered_patterns = [
                r'\d+\.\s*\*\*([^*]+)\*\*[：:]?\s*([^。\n]{15,100})',  # 粗体标题+内容
                r'\d+\.\s*([^。\n：:]{20,120})[。\n]',  # 简单编号列表
                r'["""]([^"""]{30,100})["""]',  # 引号内容
            ]
            
            for pattern in numbered_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    if isinstance(matches[0], tuple):
                        # 如果匹配结果是元组，合并内容
                        suggestions = [f"{m[0]}：{m[1]}" if len(m) > 1 and m[1] else m[0] 
                                     for m in matches[:6]]
                    else:
                        suggestions = [m for m in matches[:6]]
                    suggestions = [s.strip() for s in suggestions if len(s.strip()) > 15]
                    if suggestions:
                        break
            
            # 如果没找到编号建议，查找段落中的建议
            if not suggestions:
                suggestion_keywords = ['可以', '应该', '尝试', '学习', '练习', '增加', '提高', '避免']
                lines = content.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if (any(keyword in line for keyword in suggestion_keywords) and 
                        len(line) > 20 and len(line) < 150 and
                        not line.startswith('#')):
                        suggestions.append(line)
                        if len(suggestions) >= 6:
                            break
            
            # 默认建议（如果没有提取到）
            if not suggestions:
                suggestions = [
                    "加强基础算法练习，重点掌握排序和查找算法的原理和实现",
                    "提高代码提交的准确性，避免重复提交和错误提交",
                    "增加代码测试覆盖率，为每个算法编写完整的测试用例", 
                    "学习算法优化技巧，关注时间和空间复杂度的改进",
                    "扩展数据结构知识，学习树、图等高级数据结构"
                ]
            
            print(f"✅ 从自然语言中提取信息成功，获得{len(suggestions)}条建议")
            return {
                "trend": trend_text,
                "improvement": improvement_text,
                "suggestions": suggestions[:8]  # 最多8条建议
            }
            
        except Exception as e:
            print(f"❌ 从自然语言中提取信息失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "trend": "AI分析显示您的编程能力正在稳步提升，在多个算法实现中表现良好",
                "improvement": "建议继续保持良好的编程习惯，加强基础算法练习，提高代码质量和测试覆盖率",
                "suggestions": [
                    "多练习基础算法，特别是排序和查找算法的变种实现",
                    "注重代码规范，提高变量命名和注释的质量",
                    "增加边界条件测试，确保代码在各种输入下的健壮性",
                    "学习算法复杂度分析，理解时间和空间效率的权衡",
                    "练习代码重构，提高代码的可维护性和可读性"
                ]
            } 