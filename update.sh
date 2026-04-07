#!/bin/bash

set -e  # 任何命令失败都会退出脚本

echo "=========================================="
echo "开始更新 CodeSense 应用"
echo "=========================================="

# 1. 拉取最新代码
echo ""
echo "📥 从 GitHub 拉取代码..."
git pull origin main
if [ $? -eq 0 ]; then
    echo "✓ 代码拉取成功"
else
    echo "✗ 代码拉取失败"
    exit 1
fi

# 2. 更新 Python 依赖
echo ""
echo "📦 更新 Python 依赖..."
pip install -r requirements.txt --no-cache-dir
if [ $? -eq 0 ]; then
    echo "✓ 依赖更新成功"
else
    echo "✗ 依赖更新失败"
    exit 1
fi

# 3. 重启 Systemd 服务
echo ""
echo "🔄 重启应用服务..."
sudo systemctl restart codesense
if [ $? -eq 0 ]; then
    echo "✓ 服务重启成功"
else
    echo "✗ 服务重启失败"
    exit 1
fi

# 4. 检查服务状态
echo ""
echo "📊 检查服务状态..."
systemctl status codesense --no-pager

echo ""
echo "=========================================="
echo "✅ 更新完成！"
echo "=========================================="
