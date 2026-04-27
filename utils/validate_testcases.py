"""
测试用例验证器
在 AI 生成作业后，自动生成多套解题代码并通过沙箱验证测试用例的正确性。
"""
import json
import logging
import requests
from typing import List, Dict

from services.api_keys import api_keys
from utils.sandbox_runner import run_test_cases

logger = logging.getLogger(__name__)


def _generate_solution_code(description: str, solution_index: int, api_key: str) -> str:
    """
    调用 AI 生成一套 C++ 解题代码。
    solution_index 用于引导 AI 生成不同风格的代码。
    """
    style_hints = [
        "请使用简洁直接的实现方式，优先使用标准库函数。",
        "请使用详细、带注释的实现方式，变量命名清晰易懂。",
        "请使用高效的实现方式，注意边界条件处理。",
    ]
    style = style_hints[solution_index % len(style_hints)]

    prompt = f"""你是一位C++编程专家。请根据以下题目描述，编写一个完整的、可编译运行的 C++ 解题程序。

{style}

## 重要要求
1. 程序必须通过 stdin 读取输入，通过 stdout 输出结果
2. 必须包含 `#include` 和 `int main()` 
3. 只输出纯 C++ 代码，不要输出任何解释文字、Markdown 标记或代码块标记（如 ```）
4. 确保程序能处理题目中描述的所有边界情况

## 题目描述
{description}
"""

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "glm-4-flash",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个C++编程专家。你只输出纯C++源代码，"
                        "不添加任何Markdown标记、代码块标记或解释文字。"
                        "确保代码可以直接编译运行。"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5 + solution_index * 0.15,  # 不同温度产生不同方案
            "max_tokens": 2000
        }
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            # 清理可能的 Markdown 代码块标记
            if content.startswith("```cpp"):
                content = content[6:]
            elif content.startswith("```c++"):
                content = content[6:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return content.strip()
        else:
            logger.error(f"AI生成代码失败: HTTP {response.status_code}")
            return ""
    except Exception as e:
        logger.error(f"AI生成代码异常: {str(e)}")
        return ""


def validate_test_cases(
    description: str,
    test_cases: List[Dict],
    num_solutions: int = 2
) -> Dict:
    """
    验证测试用例的正确性。

    流程：
    1. 调用 AI 生成 num_solutions 套 C++ 解题代码
    2. 逐套使用沙箱执行，验证是否全部通过测试用例
    3. 返回验证结果

    参数：
        description: 题目描述（Markdown）
        test_cases: 测试用例列表 [{'input_data': str, 'expected_output': str, 'is_public': bool}]
        num_solutions: 生成的解题代码数量（默认2）

    返回：
        {
            'valid': bool,              # 是否全部通过
            'solutions': [              # 每套代码的验证详情
                {
                    'index': int,
                    'code': str,         # 生成的代码
                    'passed': int,
                    'total': int,
                    'status': str,       # passed/partial/failed/compile_error
                    'compile_error': str,
                    'details': [...]
                }
            ],
            'summary': str              # 简要说明
        }
    """
    if not test_cases:
        return {
            'valid': False,
            'solutions': [],
            'summary': '没有测试用例可供验证'
        }

    api_key = api_keys.get_key('zhipu')
    if not api_key:
        return {
            'valid': False,
            'solutions': [],
            'summary': 'AI服务未配置，无法生成验证代码'
        }

    solutions = []
    all_passed = True

    for i in range(num_solutions):
        logger.info(f"正在生成第 {i + 1}/{num_solutions} 套验证代码...")
        code = _generate_solution_code(description, i, api_key)

        if not code:
            solutions.append({
                'index': i + 1,
                'code': '',
                'passed': 0,
                'total': len(test_cases),
                'status': 'error',
                'compile_error': 'AI 未能生成有效代码',
                'details': []
            })
            all_passed = False
            continue

        # 使用沙箱运行测试
        logger.info(f"正在沙箱中验证第 {i + 1} 套代码...")
        sandbox_result = run_test_cases(code, test_cases)

        solution_info = {
            'index': i + 1,
            'code': code,
            'passed': sandbox_result.get('passed', 0),
            'total': sandbox_result.get('total', len(test_cases)),
            'status': sandbox_result.get('status', 'error'),
            'compile_error': sandbox_result.get('compile_error', ''),
            'details': sandbox_result.get('details', [])
        }
        solutions.append(solution_info)

        if sandbox_result.get('status') != 'passed':
            all_passed = False

    # 生成摘要
    passed_count = sum(1 for s in solutions if s['status'] == 'passed')
    if all_passed:
        summary = f'验证通过！{num_solutions} 套 AI 生成的代码均通过了所有 {len(test_cases)} 个测试用例。'
    elif passed_count > 0:
        summary = (
            f'部分通过：{passed_count}/{num_solutions} 套代码通过了全部测试用例，'
            f'请检查未通过的代码和测试用例是否正确。'
        )
    else:
        summary = (
            f'验证失败：{num_solutions} 套 AI 生成的代码均未能通过全部测试用例。'
            f'测试用例可能存在错误，请检查后重新验证。'
        )

    return {
        'valid': all_passed,
        'solutions': solutions,
        'summary': summary
    }


def auto_generate_expected_outputs(
    description: str,
    test_inputs: List[Dict],
) -> Dict:
    """
    自动生成测试用例的期望输出。

    流程：
    1. 调用 AI 生成 2 套 C++ 解题代码
    2. 用沙箱分别运行两套代码，对每个测试输入取输出
    3. 如果两套代码对同一输入产生相同输出 → 采用该输出
    4. 如果不同 → 标记该用例为"不确定"

    参数：
        description: 题目 Markdown 描述
        test_inputs: [{'input_data': str, 'is_public': bool}, ...]

    返回：
        {
            'success': bool,
            'test_cases': [
                {
                    'input_data': str,
                    'expected_output': str,   # 共识输出（两套代码结果一致时）
                    'is_public': bool,
                    'consensus': bool,         # 两套代码是否一致
                }
            ],
            'solutions': [{'index': int, 'code': str, 'compiled': bool}, ...],
            'summary': str,
        }
    """
    if not test_inputs:
        return {
            'success': False,
            'test_cases': [],
            'solutions': [],
            'summary': '没有测试输入',
        }

    api_key = api_keys.get_key('zhipu')
    if not api_key:
        return {
            'success': False,
            'test_cases': [],
            'solutions': [],
            'summary': 'AI服务未配置',
        }

    # ---------- 1. 生成 2 套解题代码 ----------
    codes = []
    solution_info = []
    for i in range(2):
        logger.info(f"正在生成第 {i+1}/2 套解题代码...")
        code = _generate_solution_code(description, i, api_key)
        codes.append(code)
        solution_info.append({'index': i + 1, 'code': code, 'compiled': False})

    # ---------- 2. 为每套代码构造"伪测试用例"运行沙箱 ----------
    # 期望输出设为空字符串，我们只关心 actual_output
    dummy_cases = [
        {
            'id': idx + 1,
            'input_data': tc.get('input_data', ''),
            'expected_output': '',   # 不比对
            'is_public': tc.get('is_public', False),
        }
        for idx, tc in enumerate(test_inputs)
    ]

    all_outputs = []  # all_outputs[solution_idx] = [output_for_case_0, output_for_case_1, ...]

    for i, code in enumerate(codes):
        if not code:
            all_outputs.append([None] * len(test_inputs))
            continue
        logger.info(f"正在沙箱运行第 {i+1} 套代码...")
        result = run_test_cases(code, dummy_cases)

        if not result.get('compile_success', False):
            logger.warning(f"第 {i+1} 套代码编译失败: {result.get('compile_error', '')}")
            all_outputs.append([None] * len(test_inputs))
            continue

        solution_info[i]['compiled'] = True
        outputs = []
        for detail in result.get('details', []):
            raw = detail.get('actual_output', '')
            # 标准化（去除末尾换行和空白）
            normalized = raw.strip()
            if detail.get('error'):
                outputs.append(None)  # 运行时错误
            else:
                outputs.append(normalized)
        # 如果 details 数量不足，补 None
        while len(outputs) < len(test_inputs):
            outputs.append(None)
        all_outputs.append(outputs)

    # ---------- 3. 取共识 ----------
    validated_cases = []
    consensus_count = 0
    for idx, tc in enumerate(test_inputs):
        out_a = all_outputs[0][idx] if len(all_outputs) > 0 else None
        out_b = all_outputs[1][idx] if len(all_outputs) > 1 else None

        if out_a is not None and out_b is not None and out_a == out_b:
            # 两套代码输出一致 → 采用
            validated_cases.append({
                'input_data': tc.get('input_data', ''),
                'expected_output': out_a,
                'is_public': tc.get('is_public', False),
                'consensus': True,
            })
            consensus_count += 1
        else:
            # 不一致或某套代码失败 → 取第一套成功的输出，标记为不确定
            fallback = out_a if out_a is not None else (out_b if out_b is not None else '')
            validated_cases.append({
                'input_data': tc.get('input_data', ''),
                'expected_output': fallback,
                'is_public': tc.get('is_public', False),
                'consensus': False,
            })

    # ---------- 4. 摘要 ----------
    total = len(test_inputs)
    compiled_count = sum(1 for s in solution_info if s['compiled'])
    if compiled_count == 0:
        summary = '两套 AI 代码均编译失败，无法自动生成期望输出。请手动填写。'
        success = False
    elif consensus_count == total:
        summary = f'验证完成！2 套代码对全部 {total} 个用例输出一致，已自动填充期望输出。'
        success = True
    else:
        summary = (
            f'部分验证：{consensus_count}/{total} 个用例的两套代码输出一致，'
            f'已自动填充。其余用例请手动检查。'
        )
        success = True  # 部分成功也算可用

    return {
        'success': success,
        'test_cases': validated_cases,
        'solutions': solution_info,
        'summary': summary,
    }
