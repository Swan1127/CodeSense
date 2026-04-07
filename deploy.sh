#!/bin/bash

# 云端部署脚本 - 首次部署使用

set -e

echo "=========================================="
echo "CodeSense 首次部署脚本"
echo "=========================================="

# 1. 检查 .env 文件
echo ""
echo "🔍 检查环境配置..."
if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在，从 .env.example 创建..."
    cp .env.example .env
    echo "✓ 已创建 .env 文件，请编辑并填入实际配置"
    echo "  编辑命令: nano .env"
    exit 1
else
    echo "✓ .env 文件已存在"
fi

# 2. 创建虚拟环境（如果不存在）
echo ""
echo "🐍 检查 Python 虚拟环境..."
if [ ! -d venv ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    echo "✓ 虚拟环境创建成功"
else
    echo "✓ 虚拟环境已存在"
fi

# 3. 激活虚拟环境并安装依赖
echo ""
echo "📦 安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
echo "✓ 依赖安装成功"

# 4. 初始化数据库
echo ""
echo "🗄️  初始化数据库..."
python -c "from app import app; app.app_context().push(); from models import db; db.create_all(); print('✓ 数据库初始化成功')"

# 5. 创建必要的目录
echo ""
echo "📁 创建必要的目录..."
mkdir -p logs uploads flask_session
echo "✓ 目录创建成功"

echo ""
echo "=========================================="
echo "✅ 部署准备完成！"
echo "=========================================="
echo ""
echo "后续步骤："
echo "1. 编辑 .env 文件配置数据库和 API 密钥"
echo "2. 运行: python app.py (本地测试)"
echo "3. 或配置 Systemd 服务进行生产部署"
