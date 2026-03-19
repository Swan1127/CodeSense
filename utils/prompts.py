"""
AI编程助手提示词管理模块
用于管理不同模式下的提示词模板
"""



class PromptManager:
    """提示词管理器"""
    
    @staticmethod
    def get_basic_analysis_prompt(code: str, assignment_title: str = None, assignment_description: str = None) -> str:
        """
        获取基础模式的代码分析提示词
        用于生成结构化的代码评估报告
        """
        base_prompt = """请分析以下代码并提供结构化的评估报告。

请从以下几个维度进行评估：
1. 算法能力 (algorithm_score): 算法逻辑的正确性和完整性
2. 代码风格 (style_score): 代码格式、命名规范、注释质量
3. 功能实现 (functionality_score): 功能的完整性和正确性
4. 效率优化 (efficiency_score): 代码的执行效率和资源使用

每项评分范围：60-95分，重在鼓励学习。

请返回JSON格式，包含以下字段：
{
  "algorithm_score": 数字,
  "style_score": 数字,
  "functionality_score": 数字,
  "efficiency_score": 数字,
  "overall_feedback": "总体评价文本",
  "suggestions": ["建议1", "建议2", "建议3"]
}"""

        if assignment_title:
            base_prompt += f"\n\n题目要求: {assignment_title}"
        if assignment_description:
            base_prompt += f"\n题目描述: {assignment_description}"
            
        base_prompt += f"\n\n要分析的代码:\n```cpp\n{code}\n```"
        
        return base_prompt
    
    @staticmethod
    def get_guidance_prompt(code: str, assignment_title: str = None, assignment_description: str = None) -> str:
        """
        获取高级模式的指导性提示词
        用于提供循循善诱的编程指导，不直接给出答案
        """
        guidance_prompt = """你是一位幽默风趣的编程导师🧙‍♂️。请用1-2句话给出简洁有趣的指导建议。

要求：只输出纯文本，不使用markdown格式，不分段，用表情符号让建议更生动有趣。

示例输出：
不错的开始！💡 试试加个循环让数据跳个舞，你已经在正确路上了🚀

---"""

        # 根据不同题目类型提供针对性的引导提示
        if assignment_title:
            if "冒泡排序" in assignment_title:
                guidance_prompt += "\n🫧 **冒泡提示**: 像汽水里的气泡一样，大数字要慢慢'冒'到后面哦！"
            elif "快速排序" in assignment_title:
                guidance_prompt += "\n⚡ **快排提示**: 找个'老大'当基准，小弟们站左边，大哥们站右边！"
            elif "二分查找" in assignment_title or "折半查找" in assignment_title:
                guidance_prompt += "\n🔍 **二分提示**: 就像猜数字游戏，每次都猜中间的！"
            elif "递归" in assignment_title:
                guidance_prompt += "\n🪆 **递归提示**: 像俄罗斯套娃，大问题装着小问题！"

        guidance_prompt += f"""

题目信息：
题目: {assignment_title or '编程练习'}
{f'描述: {assignment_description}' if assignment_description else ''}

学生的代码：
```cpp
{code}
```

请基于以上代码，提供循循善诱的指导建议。记住，我们的目标是帮助学生独立思考和解决问题，而不是替他们完成作业。"""

        return guidance_prompt

    @staticmethod
    def get_debugging_prompt(code: str, assignment_title: str = None) -> str:
        """
        获取调试指导提示词
        用于帮助学生发现和修复代码问题
        """
        return f"""你是一位编程调试专家。学生的代码可能存在一些问题，请帮助他们学会自己发现和解决问题。

指导方式：
1. 不要直接指出错误所在行
2. 引导学生检查特定的方面
3. 提供调试思路和方法
4. 鼓励学生养成良好的调试习惯

题目: {assignment_title or '编程练习'}

代码:
```cpp
{code}
```

请提供调试指导建议。"""

    @staticmethod
    def get_optimization_prompt(code: str, assignment_title: str = None) -> str:
        """
        获取代码优化指导提示词
        用于帮助学生改进代码质量
        """
        return f"""你是一位代码优化顾问。学生的代码基本能够工作，现在希望学会如何让代码更优雅、更高效。

优化指导原则：
1. 先肯定代码的正确性
2. 引导学生思考改进的方向
3. 提供优化思路而不是具体实现
4. 注重代码可读性和维护性

题目: {assignment_title or '编程练习'}

代码:
```cpp
{code}
```

请提供优化指导建议。"""

    @staticmethod  
    def get_learning_path_prompt(code: str, assignment_title: str = None) -> str:
        """
        获取学习路径建议提示词
        用于为学生规划后续学习方向
        """
        return f"""你是一位编程学习规划师。基于学生当前的代码水平，请为他们规划合适的学习路径。

规划原则：
1. 评估学生当前的编程水平
2. 识别需要加强的知识点
3. 推荐循序渐进的学习内容
4. 提供实践建议

当前练习: {assignment_title or '编程练习'}

学生代码:
```cpp
{code}
```

请提供个性化的学习建议。"""


# 全局实例
prompt_manager = PromptManager()
