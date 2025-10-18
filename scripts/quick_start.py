#!/usr/bin/env python3
"""
快速启动脚本
自动检查并配置开发环境
"""
import os
import sys
import secrets
from pathlib import Path
import shutil

# 项目根目录
project_root = Path(__file__).parent.parent


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_env_file():
    """检查并创建.env文件"""
    print_header("检查环境配置")
    
    env_file = project_root / '.env'
    env_example = project_root / 'env.example'
    
    if env_file.exists():
        print("✅ .env 文件已存在")
        return True
    
    print("📝 .env 文件不存在，开始创建...")
    
    if not env_example.exists():
        print("⚠️  env.example 模板文件不存在")
        print("   手动创建 .env 文件...")
        create_basic_env(env_file)
    else:
        print("📋 复制 env.example 为 .env")
        shutil.copy(env_example, env_file)
        update_env_file(env_file)
    
    print("✅ .env 文件创建成功")
    return True


def create_basic_env(env_file):
    """创建基础.env文件"""
    secret_key = secrets.token_hex(32)
    
    content = f"""# Flask配置
FLASK_CONFIG=development

# 应用密钥（自动生成）
SECRET_KEY={secret_key}

# 数据库配置（开发环境使用SQLite，不需要设置）
# DEV_DATABASE_URL=mysql+pymysql://root:password@localhost:3306/student_code_review

# AI API配置
ZHIPU_API_KEY=
# OPENAI_API_KEY=

# Cookie安全设置
SECURE_COOKIES=false
"""
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(content)


def update_env_file(env_file):
    """更新.env文件中的SECRET_KEY"""
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 如果SECRET_KEY是示例值，则替换为真实密钥
    if 'your-secret-key' in content or 'SECRET_KEY=' not in content:
        secret_key = secrets.token_hex(32)
        
        if 'SECRET_KEY=' in content:
            # 替换现有的SECRET_KEY
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('SECRET_KEY='):
                    lines[i] = f'SECRET_KEY={secret_key}'
                    break
            content = '\n'.join(lines)
        else:
            # 添加SECRET_KEY
            content = f'SECRET_KEY={secret_key}\n' + content
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"🔑 已生成新的 SECRET_KEY")


def check_dependencies():
    """检查依赖包"""
    print_header("检查依赖包")
    
    required_packages = [
        'flask',
        'flask_sqlalchemy',
        'python-dotenv',
        'pymysql',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (未安装)")
            missing.append(package)
    
    if missing:
        print("\n⚠️  缺少依赖包，请运行：")
        print(f"   pip install -r requirements.txt")
        return False
    
    return True


def check_directories():
    """检查并创建必要的目录"""
    print_header("检查项目目录")
    
    required_dirs = [
        'logs',
        'uploads',
        'flask_session',
        'instance',
    ]
    
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 创建目录: {dir_name}")
        else:
            print(f"✅ {dir_name}")
    
    # 创建.gitkeep文件
    uploads_gitkeep = project_root / 'uploads' / '.gitkeep'
    if not uploads_gitkeep.exists():
        uploads_gitkeep.touch()
    
    return True


def run_security_check():
    """运行安全检查"""
    print_header("运行安全检查")
    
    security_script = project_root / 'scripts' / 'security_check.py'
    
    if not security_script.exists():
        print("⚠️  安全检查脚本不存在，跳过")
        return True
    
    try:
        # 运行安全检查脚本
        import subprocess
        result = subprocess.run(
            [sys.executable, str(security_script)],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print("⚠️  安全检查发现问题，但不影响开发环境启动")
            return True
        
        return True
        
    except Exception as e:
        print(f"⚠️  安全检查失败: {e}")
        return True


def show_next_steps():
    """显示下一步操作"""
    print_header("🎉 环境配置完成！")
    
    print("\n📝 下一步操作：\n")
    print("1. 配置 AI API 密钥（可选）：")
    print("   编辑 .env 文件，填入 ZHIPU_API_KEY 或 OPENAI_API_KEY")
    print()
    print("2. 初始化数据库：")
    print("   python init_db.py")
    print()
    print("3. 启动应用：")
    print("   python app.py")
    print("   或: flask run")
    print()
    print("4. 访问应用：")
    print("   http://127.0.0.1:5000")
    print()
    print("💡 提示：")
    print("  - 开发环境默认使用 SQLite 数据库")
    print("  - 如需使用 MySQL，在 .env 中设置 DEV_DATABASE_URL")
    print("  - AI 功能需要配置 API 密钥才能使用")
    print()
    print("📖 文档：")
    print("  - 部署指南: DEPLOYMENT.md")
    print("  - 安全配置: SECURITY.md")
    print("  - 项目说明: README.md")
    print()


def main():
    """主函数"""
    print_header("🚀 学生程序设计能力评价系统 - 快速启动")
    
    print("\n正在配置开发环境...\n")
    
    # 执行检查和配置
    steps = [
        ("创建环境配置", check_env_file),
        ("检查依赖包", check_dependencies),
        ("创建必要目录", check_directories),
        ("安全检查", run_security_check),
    ]
    
    for step_name, step_func in steps:
        try:
            if not step_func():
                print(f"\n❌ {step_name} 失败")
                return 1
        except Exception as e:
            print(f"\n❌ {step_name} 出错: {e}")
            return 1
    
    # 显示下一步
    show_next_steps()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

