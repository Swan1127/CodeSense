"""
沙箱代码执行引擎
在受限环境中编译并运行 C++ 代码，对比测试用例输出。
依赖：系统已安装 g++ (MinGW on Windows / g++ on Linux)
"""
import os
import json
import subprocess
import tempfile
import platform
import re
from typing import List, Dict, Tuple

# 超时时间（秒）
COMPILE_TIMEOUT = 15
RUN_TIMEOUT = 5

# 输出长度上限（字符）
MAX_OUTPUT_LEN = 4096


def _normalize_output(s: str) -> str:
    """标准化输出：统一换行符、去除行尾空白、去除末尾空行"""
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.rstrip() for line in s.split('\n')]
    # 去除末尾空行
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def _find_compiler() -> str:
    """查找系统中可用的 C++ 编译器"""
    candidates = ['g++', 'g++.exe', 'c++']
    # Windows 常见 MinGW 路径
    windows_paths = [
        r'C:\MinGW\bin\g++.exe',
        r'C:\mingw64\bin\g++.exe',
        r'C:\Program Files\mingw-w64\x86_64-8.1.0-posix-seh-rt_v6-rev0\mingw64\bin\g++.exe',
        r'C:\msys64\mingw64\bin\g++.exe',
        r'C:\msys64\ucrt64\bin\g++.exe',
        # Anaconda/Miniconda 路径
        os.path.join(os.environ.get('CONDA_PREFIX', ''), 'Library', 'mingw-w64', 'bin', 'g++.exe'),
        os.path.join(os.environ.get('CONDA_PREFIX', ''), 'Library', 'bin', 'g++.exe'),
        # 用户可能安装在 E 盘
        r'E:\anaconda\Library\mingw-w64\bin\g++.exe',
        r'E:\anaconda\envs\student-eval\Library\mingw-w64\bin\g++.exe',
    ]
    if platform.system() == 'Windows':
        for path in windows_paths:
            if os.path.isfile(path):
                return path
    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def compile_cpp(source_code: str, work_dir: str) -> Tuple[bool, str, str]:
    """
    编译 C++ 源码。
    返回 (success, exe_path, error_message)
    """
    compiler = _find_compiler()
    if not compiler:
        return False, '', '系统未安装 C++ 编译器（g++），无法运行测试用例。请联系管理员安装 MinGW/g++。'

    src_path = os.path.join(work_dir, 'solution.cpp')
    exe_path = os.path.join(work_dir, 'solution.exe' if platform.system() == 'Windows' else 'solution')

    with open(src_path, 'w', encoding='utf-8') as f:
        f.write(source_code)

    try:
        # 注入编译器目录到 PATH，解决 Windows 下 DLL 缺失问题
        env = os.environ.copy()
        compiler_dir = os.path.dirname(compiler)
        env['PATH'] = compiler_dir + os.pathsep + env.get('PATH', '')

        result = subprocess.run(
            [compiler, src_path, '-o', exe_path, '-std=c++17', '-O2', '-Wall'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=COMPILE_TIMEOUT,
            cwd=work_dir,
            env=env
        )
        if result.returncode != 0:
            err = result.stderr[:2000] if result.stderr else '编译失败（无错误信息）'
            return False, '', err
        return True, exe_path, ''
    except subprocess.TimeoutExpired:
        return False, '', f'编译超时（超过 {COMPILE_TIMEOUT} 秒）'
    except Exception as e:
        return False, '', f'编译过程出错：{str(e)}'


def run_single_test(exe_path: str, input_data: str, expected_output: str, work_dir: str) -> Dict:
    """
    运行单个测试用例。
    返回结果字典：{passed, actual_output, expected_output, error, time_ms}
    """
    result = {
        'passed': False,
        'actual_output': '',
        'expected_output': expected_output,
        'error': None,
        'time_ms': 0,
    }
    try:
        import time
        start = time.time()
        # 运行编译后的程序（同样注入 PATH，解决运行时 DLL 依赖问题）
        env = os.environ.copy()
        compiler = _find_compiler()
        if compiler:
            env['PATH'] = os.path.dirname(compiler) + os.pathsep + env.get('PATH', '')

        proc = subprocess.run(
            [exe_path],
            input=input_data,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=RUN_TIMEOUT,
            cwd=work_dir,
            env=env
        )
        elapsed = int((time.time() - start) * 1000)
        result['time_ms'] = elapsed

        actual = proc.stdout[:MAX_OUTPUT_LEN]
        result['actual_output'] = actual

        if proc.returncode != 0:
            stderr = proc.stderr[:500] if proc.stderr else ''
            result['error'] = f'程序运行时错误（退出码 {proc.returncode}）' + (f'：{stderr}' if stderr else '')
            return result

        # 比较输出（标准化后）
        if _normalize_output(actual) == _normalize_output(expected_output):
            result['passed'] = True
        return result

    except subprocess.TimeoutExpired:
        result['error'] = f'运行超时（超过 {RUN_TIMEOUT} 秒）'
        return result
    except Exception as e:
        result['error'] = f'运行出错：{str(e)}'
        return result


def run_test_cases(source_code: str, test_cases: List[Dict]) -> Dict:
    """
    主入口：编译并对所有测试用例运行代码。

    参数：
        source_code: C++ 源代码字符串
        test_cases: list of {'input_data': str, 'expected_output': str, 'id': int, 'is_public': bool}

    返回：
        {
            'compiler_available': bool,
            'compile_success': bool,
            'compile_error': str,
            'passed': int,
            'total': int,
            'status': 'passed'|'partial'|'failed'|'compile_error'|'no_cases'|'unavailable',
            'details': [per-case result dicts],
        }
    """
    if not test_cases:
        return {
            'compiler_available': True,
            'compile_success': False,
            'compile_error': '',
            'passed': 0,
            'total': 0,
            'status': 'no_cases',
            'details': [],
        }

    with tempfile.TemporaryDirectory() as work_dir:
        # 编译
        ok, exe_path, compile_err = compile_cpp(source_code, work_dir)

        if '系统未安装' in compile_err or not _find_compiler():
            return {
                'compiler_available': False,
                'compile_success': False,
                'compile_error': compile_err,
                'passed': 0,
                'total': len(test_cases),
                'status': 'unavailable',
                'details': [],
            }

        if not ok:
            return {
                'compiler_available': True,
                'compile_success': False,
                'compile_error': compile_err,
                'passed': 0,
                'total': len(test_cases),
                'status': 'compile_error',
                'details': [],
            }

        # 运行每个测试用例
        details = []
        passed = 0
        for idx, tc in enumerate(test_cases):
            res = run_single_test(
                exe_path,
                tc.get('input_data', ''),
                tc.get('expected_output', ''),
                work_dir
            )
            res['case_id'] = tc.get('id', idx + 1)
            res['is_public'] = tc.get('is_public', False)
            res['order_index'] = idx + 1
            if res['passed']:
                passed += 1
            details.append(res)

        total = len(test_cases)
        if passed == total:
            status = 'passed'
        elif passed == 0:
            status = 'failed'
        else:
            status = 'partial'

        return {
            'compiler_available': True,
            'compile_success': True,
            'compile_error': '',
            'passed': passed,
            'total': total,
            'status': status,
            'details': details,
        }
