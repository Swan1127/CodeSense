#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新数据库中的系统配置"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import SystemConfig

def update_system_configs():
    """更新系统配置中的旧名称"""
    with app.app_context():
        print("正在更新数据库中的系统配置...\n")

        # 定义需要更新的配置
        updates = [
            {
                'key': 'site_name',
                'value': 'CodeSense 酷森思',
                'description': '网站名称'
            },
            {
                'key': 'login_message',
                'value': '欢迎登录 CodeSense 酷森思',
                'description': '登录页面欢迎消息'
            },
            {
                'key': 'site_description',
                'value': '一个基于人工智能的代码评估平台',
                'description': '网站描述'
            }
        ]

        updated_count = 0

        for config_data in updates:
            config = SystemConfig.query.filter_by(key=config_data['key']).first()

            if config:
                old_value = config.value
                config.value = config_data['value']
                config.description = config_data['description']
                print(f"[更新] {config_data['key']}")
                print(f"  旧值: {old_value}")
                print(f"  新值: {config.value}\n")
                updated_count += 1
            else:
                # 如果配置不存在，创建它
                config = SystemConfig(
                    key=config_data['key'],
                    value=config_data['value'],
                    description=config_data['description'],
                    type='string'
                )
                db.session.add(config)
                print(f"[创建] {config_data['key']}: {config_data['value']}\n")
                updated_count += 1

        try:
            db.session.commit()
            print(f"\n成功更新 {updated_count} 个配置项！")
            print("\n请重启应用以使更改生效。")
        except Exception as e:
            db.session.rollback()
            print(f"\n更新失败: {str(e)}")
            return False

        return True

if __name__ == '__main__':
    print("="*50)
    print("系统配置更新工具")
    print("="*50)
    print()

    success = update_system_configs()

    if success:
        print("\n✓ 更新完成！")
        sys.exit(0)
    else:
        print("\n✗ 更新失败！")
        sys.exit(1)
