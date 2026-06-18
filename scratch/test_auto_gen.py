import os
import sys

# Change working directory to project root
sys.path.insert(0, os.path.abspath('e:/CodeSense/源代码'))
os.chdir('e:/CodeSense/源代码')

from utils.validate_testcases import auto_generate_expected_outputs
import json

description = """
### 作业描述
给定一组字符及其对应的频率，构建一个哈夫曼树，并输出每个字符的哈夫曼编码。
哈夫曼树是一种带权路径长度最短的二叉树，用于数据压缩。

### 输入格式
第一行包含一个正整数 n（2 ≤ n ≤ 20），表示字符数量。
接下来 n 行，每行包含两个整数，第一个整数表示字符的ASCII码值（0 ≤ ASCII码值 ≤ 255），第二个整数表示该字符的频率（1 ≤ 频率 ≤ 100）。

### 输出格式
输出哈夫曼树的节点，格式为 '字符: 频率: 左/右'，其中 '字符' 是字符的ASCII码值对应的字符，'频率' 是该字符的频率，'左/右' 表示该节点是左子节点还是右子节点。
每个节点占一行，从根节点开始，先输出根节点，然后按照从左到右的顺序输出子节点。
"""

test_inputs = [
    {
        "input_data": "5\n65 5\n66 9\n67 12\n68 13\n69 16\n",
        "is_public": True,
        "id": 1
    }
]

result = auto_generate_expected_outputs(description, test_inputs)

print("SUCCESS:", result['success'])
print("SUMMARY:", result['summary'])
for i, sol in enumerate(result['solutions']):
    print(f"\n--- SOLUTION {i+1} CODE ---")
    print(sol['code'])
    print(f"--- SOLUTION {i+1} COMPILED: {sol['compiled']} ---")

for i, tc in enumerate(result['test_cases']):
    print(f"\n--- TEST CASE {i+1} EXPECTED OUTPUT ---")
    print(repr(tc['expected_output']))
    print(f"CONSENSUS: {tc['consensus']}")
