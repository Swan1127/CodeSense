#!/usr/bin/env python3
"""
检查API和应用状态
"""
import requests
import json
import os

def main():
    print("🔍 检查系统状态...")
    
    # 1. 检查环境变量
    api_key = os.environ.get('ZHIPU_API_KEY', '')
    print(f"🔑 API Key: {'已设置' if api_key else '未设置'} ({len(api_key)} 字符)")
    
    # 2. 检查应用状态
    print("\n🌐 检查Flask应用状态...")
    try:
        response = requests.get('http://127.0.0.1:5000/login', timeout=5)
        print(f"✅ 应用正常运行 - HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 应用连接失败: {e}")
        return
    
    # 3. 直接测试API
    if not api_key:
        print("❌ 无法测试API - API Key未设置")
        return
        
    print("\n🧪 直接测试智谱AI API...")
    url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'glm-4.5-flash',
        'messages': [{'role': 'user', 'content': '测试：请回复OK'}],
        'max_tokens': 10
    }
    
    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)
        print(f"📈 响应状态: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            message = result['choices'][0]['message']
            content = message.get('content', '') or message.get('reasoning_content', '')
            print(f"✅ API正常工作，回复: {content.strip()}")
            
            # 4. 测试能力趋势分析
            print("\n📊 测试能力趋势分析...")
            from services.ai_evaluator import AIEvaluator
            
            evaluator = AIEvaluator(api_key)
            test_data = [{
                'assignment_title': '测试作业',
                'code': 'print("test")',
                'score': 5,
                'submitted_at': '2024-09-25'
            }]
            
            result = evaluator.analyze_ability_trend(test_data)
            print(f"✅ 能力分析成功!")
            print(f"📋 趋势: {result.get('trend', '')[:80]}...")
            print(f"📋 建议数量: {len(result.get('suggestions', []))}")
            
        else:
            print(f"❌ API错误: {r.text[:200]}")
            
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()







