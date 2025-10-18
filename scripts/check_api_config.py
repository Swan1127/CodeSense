#!/usr/bin/env python
"""
API配置检查和测试脚本
"""
import os
import sys
import traceback
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

def check_env_file():
    """检查.env文件是否存在和配置是否完整"""
    print_colored("\n==== 检查.env文件 ====", "blue")
    
    # 尝试加载环境变量
    load_dotenv()
    
    # 检查.env文件是否存在
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if not os.path.exists(env_path):
        print_colored("× .env文件不存在！", "red")
        return False
    
    print_colored(f"✓ .env文件位置: {env_path}", "green")
    
    # 检查关键配置项
    required_configs = {
        'DATABASE_URL': '数据库连接URL',
        'SECRET_KEY': 'Flask应用密钥',
        'ZHIPU_API_KEY': '智谱AI API密钥',
    }
    
    optional_configs = {
        'OPENAI_API_KEY': 'OpenAI API密钥',
    }
    
    missing_configs = []
    
    for key, desc in required_configs.items():
        value = os.environ.get(key)
        if not value:
            print_colored(f"× 缺少必要配置: {key} ({desc})", "red")
            missing_configs.append(key)
        else:
            # 仅显示密钥的前10个字符，其余用*替代
            if 'KEY' in key and len(value) > 10:
                masked_value = value[:10] + '*' * (len(value) - 10)
                print_colored(f"✓ 已配置 {key}: {masked_value}", "green")
            else:
                print_colored(f"✓ 已配置 {key}", "green")
    
    for key, desc in optional_configs.items():
        value = os.environ.get(key)
        if not value:
            print_colored(f"○ 可选配置未设置: {key} ({desc})", "yellow")
        else:
            if 'KEY' in key and len(value) > 10:
                masked_value = value[:10] + '*' * (len(value) - 10)
                print_colored(f"✓ 已配置 {key}: {masked_value}", "green")
            else:
                print_colored(f"✓ 已配置 {key}", "green")
    
    if missing_configs:
        print_colored(f"\n⚠️ 警告: 缺少 {len(missing_configs)} 项必要配置", "yellow")
        return False
    else:
        print_colored("\n✓ 所有必要配置已设置", "green")
        return True

def test_zhipu_api():
    """测试智谱AI API连接"""
    print_colored("\n==== 测试智谱AI API连接 ====", "blue")
    
    zhipu_key = os.environ.get("ZHIPU_API_KEY")
    if not zhipu_key:
        print_colored("× 未配置智谱AI API密钥，无法测试连接", "red")
        return False
    
    try:
        # 尝试导入zhipuai库
        try:
            import zhipuai
            from zhipuai import ZhipuAI
        except ImportError:
            print_colored("× 未安装zhipuai库，请先安装:", "red")
            print_colored("  pip install -U zhipuai", "yellow")
            return False
        
        print_colored("✓ 成功导入zhipuai库", "green")
        
        # 初始化客户端
        print_colored("尝试初始化智谱AI客户端...", "blue")
        client = ZhipuAI(api_key=zhipu_key)
        
        # 发送一个简单的测试请求
        print_colored("发送测试请求到智谱AI API...", "blue")
        response = client.chat.completions.create(
            model="glm-4.5-flash",
            messages=[
                {"role": "system", "content": "你是一个有用的助手"},
                {"role": "user", "content": "你好，这是一个API测试"}
            ],
            max_tokens=10
        )
        
        # 检查响应
        if response and hasattr(response, 'choices') and len(response.choices) > 0:
            print_colored(f"✓ API连接成功！", "green")
            print_colored(f"✓ 模型回复: {response.choices[0].message.content}", "green")
            return True
        else:
            print_colored(f"× API返回了意外的响应格式", "red")
            print(response)
            return False
            
    except Exception as e:
        print_colored(f"× 连接智谱AI API时出错: {e}", "red")
        print_colored(traceback.format_exc(), "red")
        return False

def test_openai_api():
    """测试OpenAI API连接"""
    print_colored("\n==== 测试OpenAI API连接 ====", "blue")
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print_colored("○ 未配置OpenAI API密钥，跳过测试", "yellow")
        return False
    
    try:
        # 尝试导入openai库
        try:
            import openai
            from openai import OpenAI
        except ImportError:
            print_colored("× 未安装openai库，请先安装:", "red")
            print_colored("  pip install -U openai", "yellow")
            return False
        
        print_colored("✓ 成功导入openai库", "green")
        
        # 初始化客户端
        print_colored("尝试初始化OpenAI客户端...", "blue")
        client = OpenAI(api_key=openai_key)
        
        # 发送一个简单的测试请求
        print_colored("发送测试请求到OpenAI API...", "blue")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "你是一个有用的助手"},
                {"role": "user", "content": "你好，这是一个API测试"}
            ],
            max_tokens=10
        )
        
        # 检查响应
        if response and hasattr(response, 'choices') and len(response.choices) > 0:
            print_colored(f"✓ API连接成功！", "green")
            print_colored(f"✓ 模型回复: {response.choices[0].message.content}", "green")
            return True
        else:
            print_colored(f"× API返回了意外的响应格式", "red")
            print(response)
            return False
            
    except Exception as e:
        print_colored(f"× 连接OpenAI API时出错: {e}", "red")
        print_colored(traceback.format_exc(), "red")
        return False

def main():
    """主函数"""
    print_colored("\n====== 学生代码评估系统 API配置检查 ======", "purple")
    
    # 检查.env文件
    env_ok = check_env_file()
    
    # 如果.env文件存在且配置了智谱AI密钥，测试连接
    if env_ok:
        print_colored("\n开始测试API连接...", "blue")
        
        # 测试智谱AI API
        zhipu_ok = test_zhipu_api()
        
        # 测试OpenAI API (如果已配置)
        openai_ok = test_openai_api()
        
        # 总结
        print_colored("\n====== API配置检查结果 ======", "purple")
        if zhipu_ok:
            print_colored("✓ 智谱AI API配置正确且连接成功", "green")
        else:
            print_colored("× 智谱AI API配置或连接存在问题", "red")
            
        if openai_ok:
            print_colored("✓ OpenAI API配置正确且连接成功", "green")
        elif os.environ.get("OPENAI_API_KEY"):
            print_colored("× OpenAI API配置或连接存在问题", "red")
        else:
            print_colored("○ OpenAI API未配置", "yellow")
            
        if zhipu_ok or openai_ok:
            print_colored("\n✓ 大模型评估功能应该可以正常使用", "green")
        else:
            print_colored("\n× 大模型评估功能将不可用，请检查API配置", "red")
    else:
        print_colored("\n× 由于.env配置不完整，跳过API连接测试", "red")
        print_colored("请先完成.env配置再重新运行测试", "yellow")
    
    print_colored("\n如需修改API配置，请编辑.env文件", "blue")
    print_colored("或运行: python scripts/setup_dependencies.py", "blue")

if __name__ == "__main__":
    main() 