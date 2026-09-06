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

# 3. 安装并启用独立 RQ worker
echo ""
echo "⚙️ 安装后台 RQ worker 服务..."
sudo install -m 0644 codesense-ability-worker.service /etc/systemd/system/codesense-ability-worker.service
sudo install -m 0644 codesense-submission-worker.service /etc/systemd/system/codesense-submission-worker.service
sudo systemctl daemon-reload
if grep -Eq '^(ABILITY_ANALYSIS_QUEUE_BACKEND|SUBMISSION_EVALUATION_QUEUE_BACKEND)=rq' /var/www/codesense/.env 2>/dev/null; then
    sudo systemctl enable --now codesense-ability-worker codesense-submission-worker
else
    sudo systemctl disable --now codesense-ability-worker codesense-submission-worker 2>/dev/null || true
fi

# 4. 重启 Systemd 服务
echo ""
echo "🔄 重启应用服务..."
sudo systemctl restart codesense
if [ $? -eq 0 ]; then
    echo "✓ 服务重启成功"
else
    echo "✗ 服务重启失败"
    exit 1
fi

# 5. 检查服务状态
echo ""
echo "📊 检查服务状态..."
systemctl status codesense --no-pager
if grep -Eq '^(ABILITY_ANALYSIS_QUEUE_BACKEND|SUBMISSION_EVALUATION_QUEUE_BACKEND)=rq' /var/www/codesense/.env 2>/dev/null; then
    systemctl status codesense-ability-worker codesense-submission-worker --no-pager
fi

echo ""
echo "=========================================="
echo "✅ 更新完成！"
echo "=========================================="
