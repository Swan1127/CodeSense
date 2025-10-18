#!/usr/bin/env python
"""
测试LLMEvaluator的get_llm_response方法
"""
import os
import sys
import traceback
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入LLMEvaluator
from utils.llm_evaluator import LLMEvaluator

def print_colored(text, color):
    """打印彩色文本"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'purple': '\033[95m',
        'end': '\033[0m'
    }
    
    print(f"{colors.get(color, '')}{text}{colors['end']}")

def main():
    """主函数"""
    print_colored("\n====== 测试LLMEvaluator的get_llm_response方法 ======", "purple")
    
    # 加载环境变量
    load_dotenv()
    
    try:
        # 初始化LLMEvaluator
        print_colored("正在初始化LLMEvaluator...", "blue")
        evaluator = LLMEvaluator(api_type="zhipu")
        print_colored("✓ LLMEvaluator初始化成功", "green")
        
        # 简单的测试提示
        test_prompt = """请简要介绍一下变量的概念和使用方法。"""
        
        # 调用get_llm_response方法
        print_colored("\n发送提示到大模型...", "blue")
        print_colored(f"提示内容: {test_prompt}", "blue")
        
        response = evaluator.get_llm_response(test_prompt)
        
        # 输出响应
        print_colored("\n====== 大模型响应 ======", "purple")
        print(response)
        print_colored("\n====== 测试完成 ======", "purple")
        print_colored("✓ 方法调用成功，问题已修复", "green")
        
    except Exception as e:
        print_colored(f"\n× 测试失败: {e}", "red")
        print_colored(traceback.format_exc(), "red")
        print_colored("\n问题可能尚未完全修复，请检查错误信息", "yellow")

if __name__ == "__main__":
    main() 