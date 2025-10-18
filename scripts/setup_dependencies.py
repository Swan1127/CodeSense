#!/usr/bin/env python
"""
依赖项安装和配置脚本
"""
import os
import sys
import subprocess
import platform
import importlib.util
from pathlib import Path
from dotenv import load_dotenv, set_key

# 尝试加载环境变量
load_dotenv()

def print_colored(text, color):
    """打印彩色文本"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    
    if platform.system() == 'Windows':
        # Windows终端可能不支持ANSI颜色
        print(text)
    else:
        print(f"{colors.get(color, '')}{text}{colors['end']}")

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print_colored(f"警告: 当前Python版本 {version.major}.{version.minor}.{version.micro} 可能不完全支持。推荐使用Python 3.7+", "yellow")
        return False
    else:
        print_colored(f"✓ Python版本检查通过: {version.major}.{version.minor}.{version.micro}", "green")
        return True

def install_package(package_name):
    """安装指定的包"""
    try:
        print_colored(f"正在安装 {package_name}...", "blue")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", package_name])
        print_colored(f"✓ {package_name} 安装成功", "green")
        return True
    except subprocess.CalledProcessError:
        print_colored(f"× {package_name} 安装失败", "red")
        print("尝试使用--user参数...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", package_name, "--user"])
            print_colored(f"✓ {package_name} 安装成功 (使用--user)", "green")
            return True
        except subprocess.CalledProcessError:
            print_colored(f"× {package_name} 安装失败，请手动安装", "red")
            return False

def check_package(package_name):
    """检查包是否已安装"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def check_and_install_package(package_name):
    """检查包是否安装，如果未安装则安装"""
    if check_package(package_name):
        print_colored(f"✓ {package_name} 已安装", "green")
        return True
    else:
        print_colored(f"× {package_name} 未安装", "yellow")
        return install_package(package_name)

def check_api_keys():
    """检查.env文件中的API密钥配置"""
    env_path = Path('../.env')
    
    # 检查.env文件是否存在
    if not env_path.exists():
        print_colored("× .env文件不存在", "yellow")
        return False, False
    
    # 读取.env文件
    zhipu_key = None
    openai_key = None
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('ZHIPU_API_KEY='):
                zhipu_key = line.split('=', 1)[1].strip()
            if line.startswith('OPENAI_API_KEY='):
                openai_key = line.split('=', 1)[1].strip()
    
    if zhipu_key:
        print_colored("✓ 已配置智谱AI API密钥", "green")
    else:
        print_colored("× 未配置智谱AI API密钥", "yellow")
    
    if openai_key:
        print_colored("✓ 已配置OpenAI API密钥", "green")
    else:
        print_colored("× 未配置OpenAI API密钥", "yellow")
    
    if not zhipu_key and not openai_key:
        print_colored("警告: 未配置任何API密钥，大模型评估功能将不可用", "red")
    
    return zhipu_key is not None, openai_key is not None

def setup_api_keys():
    """设置API密钥"""
    print_colored("\n==== API密钥配置 ====", "blue")
    print("大模型评估功能需要API密钥。您可以选择配置智谱AI或OpenAI的API密钥。")
    
    env_path = Path('../.env')
    
    # 如果.env文件不存在，创建它
    if not env_path.exists():
        with open(env_path, 'w') as f:
            f.write("# API密钥配置\n")
    
    # 读取现有的.env内容
    env_content = ""
    with open(env_path, 'r') as f:
        env_content = f.read()
    
    # 配置智谱AI API密钥
    setup_zhipu = input("是否配置智谱AI API密钥? (y/n): ").lower() == 'y'
    if setup_zhipu:
        zhipu_key = input("请输入智谱AI API密钥: ").strip()
        if zhipu_key:
            # 替换或添加ZHIPU_API_KEY
            if "ZHIPU_API_KEY=" in env_content:
                lines = env_content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith("ZHIPU_API_KEY="):
                        new_lines.append(f"ZHIPU_API_KEY={zhipu_key}")
                    else:
                        new_lines.append(line)
                env_content = '\n'.join(new_lines)
            else:
                env_content += f"\nZHIPU_API_KEY={zhipu_key}"
            print_colored("✓ 智谱AI API密钥已配置", "green")
    
    # 配置OpenAI API密钥
    setup_openai = input("是否配置OpenAI API密钥? (y/n): ").lower() == 'y'
    if setup_openai:
        openai_key = input("请输入OpenAI API密钥: ").strip()
        if openai_key:
            # 替换或添加OPENAI_API_KEY
            if "OPENAI_API_KEY=" in env_content:
                lines = env_content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith("OPENAI_API_KEY="):
                        new_lines.append(f"OPENAI_API_KEY={openai_key}")
                    else:
                        new_lines.append(line)
                env_content = '\n'.join(new_lines)
            else:
                env_content += f"\nOPENAI_API_KEY={openai_key}"
            print_colored("✓ OpenAI API密钥已配置", "green")
    
    # 写入更新后的.env文件
    if setup_zhipu or setup_openai:
        with open(env_path, 'w') as f:
            f.write(env_content)
        print_colored("✓ .env文件已更新", "green")

def main():
    """主函数"""
    print_colored("\n===== 学生代码评估系统依赖检查与安装 =====", "blue")
    
    # 检查Python版本
    check_python_version()
    
    # 检查并安装基础依赖
    print_colored("\n==== 检查基础依赖 ====", "blue")
    basic_packages = ["torch", "transformers", "flask", "dotenv"]
    for package in basic_packages:
        check_and_install_package(package)
    
    # 检查并安装大模型API依赖
    print_colored("\n==== 检查大模型API依赖 ====", "blue")
    print_colored("检查zhipuai...", "blue")
    zhipuai_installed = check_and_install_package("zhipuai")
    
    print_colored("检查openai...", "blue")
    openai_installed = check_and_install_package("openai")
    
    # 检查API密钥配置
    print_colored("\n==== 检查API密钥配置 ====", "blue")
    zhipu_key_exists, openai_key_exists = check_api_keys()
    
    # 如果依赖已安装但未配置API密钥，提示配置
    if (zhipuai_installed and not zhipu_key_exists) or (openai_installed and not openai_key_exists):
        setup_api_keys_prompt = input("\n是否现在配置API密钥? (y/n): ").lower() == 'y'
        if setup_api_keys_prompt:
            setup_api_keys()
    
    print_colored("\n===== 依赖检查与安装完成 =====", "green")
    if (zhipuai_installed and zhipu_key_exists) or (openai_installed and openai_key_exists):
        print_colored("✓ 大模型评估功能应该可以正常使用", "green")
    else:
        print_colored("警告: 大模型评估功能可能不可用", "yellow")
        print_colored("请确保安装zhipuai或openai库，并正确配置API密钥", "yellow")
    
    print_colored("\n运行方式: cd .. && python run.py", "blue")

if __name__ == "__main__":
    main() 