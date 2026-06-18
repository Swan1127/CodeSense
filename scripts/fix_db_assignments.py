import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Assignment, TestCase

def fix_assignments():
    app = create_app('development')
    with app.app_context():
        # 1. Fix Assignment 120: 最长公共子序列
        a120 = Assignment.query.get(120)
        if a120:
            a120.description = """### 作业描述
给定两个字符串，找出它们的最长公共子序列（LCS）。最长公共子序列是指两个序列中同时出现的最长序列，该序列的元素在原序列中保持相同的相对顺序。

请使用动态规划方法求解此问题。

### 输入格式
第一行包含两个正整数 n 和 m（1 ≤ n, m ≤ 1000），分别表示两个字符串的长度。
第二行包含第一个字符串 s1，长度为 n。
第三行包含第二个字符串 s2，长度为 m。

### 输出格式
输出一个整数，表示最长公共子序列的长度。

### 输入样例
```
6 7
AGGTAB
GXTXAYB
```

### 输出样例
```
4
```"""
            # Delete old test cases
            TestCase.query.filter_by(assignment_id=120).delete()
            # Insert new test cases
            new_cases_120 = [
                ('6 7\nAGGTAB\nGXTXAYB', '4'),
                ('6 6\nABCDGH\nAEDFHR', '3'),
                ('1 1\nA\nA', '1'),
                ('2 3\nAB\nABC', '2'),
                ('4 4\nABCD\nABCD', '4')
            ]
            for idx, (inp, out) in enumerate(new_cases_120):
                tc = TestCase(
                    assignment_id=120,
                    input_data=inp,
                    expected_output=out,
                    order_index=idx,
                    is_public=(idx == 0)
                )
                db.session.add(tc)
            print("Fixed assignment 120 successfully.")

        # 2. Fix Assignment 121: 哈夫曼树构建
        a121 = Assignment.query.get(121)
        if a121:
            a121.description = """### 作业描述
给定一个包含字符及其出现频率的列表，构建一个哈夫曼树，并输出树的每个节点的字符、频率、左孩子和右孩子的索引。
哈夫曼树是一种带权路径长度最短 of 二叉树，用于数据压缩算法。

### 输入格式
第一行包含一个整数 n（1 ≤ n ≤ 20），表示字符的数量。
接下来 n 行，每行包含一个整数和一个字符，第一个整数表示字符的频率（1 ≤ 频率 ≤ 100），第二个字符表示字符本身（字符可以是任意字符，包括空格和标点符号）。

### 输出格式
输出 n 个节点的信息，每个节点信息占一行，格式为：字符 频率 左孩子索引 右孩子索引。
如果节点是叶子节点，则左右孩子索引为 -1。

### 输入样例
```
4
5 a
3 b
2 c
4 d
```

### 输出样例
```
a 5 -1 -1
b 3 -1 -1
c 2 -1 -1
d 4 -1 -1
```

### 提示
构建哈夫曼树时，每次选择两个最小频率的节点作为新的父节点，直到所有节点都被合并为一个根节点。"""
            # Delete old test cases
            TestCase.query.filter_by(assignment_id=121).delete()
            # Insert new test cases
            new_cases_121 = [
                ('4\n5 a\n3 b\n2 c\n4 d\n', 'a 5 -1 -1\nb 3 -1 -1\nc 2 -1 -1\nd 4 -1 -1'),
                ('3\n1 a\n2 b\n3 c\n', 'a 1 -1 -1\nb 2 -1 -1\nc 3 -1 -1'),
                ('2\n1 a\n2 b\n', 'a 1 -1 -1\nb 2 -1 -1'),
                ('1\n10 a\n', 'a 10 -1 -1'),
                ('4\n5 a\n5 b\n5 c\n5 d\n', 'a 5 -1 -1\nb 5 -1 -1\nc 5 -1 -1\nd 5 -1 -1')
            ]
            for idx, (inp, out) in enumerate(new_cases_121):
                tc = TestCase(
                    assignment_id=121,
                    input_data=inp,
                    expected_output=out,
                    order_index=idx,
                    is_public=(idx == 0)
                )
                db.session.add(tc)
            print("Fixed assignment 121 successfully.")

        # 3. Fix Assignment 122: 队列的最大值
        a122 = Assignment.query.get(122)
        if a122:
            a122.description = """### 作业描述
实现一个队列，支持以下操作：
1. `push(int value)`：向队列中插入一个元素。
2. `pop()`：删除队列中的最前面元素。
3. `max()`：返回队列中当前最大元素。

队列中的元素类型为整数，且值范围在 -10000 到 10000 之间。

在实现时，需要保证 `max()` 操作的时间复杂度为 O(1)。

### 输入格式
第一行包含两个整数 n 和 m，其中 n 表示操作的个数，m 表示操作类型（1 表示 push，2 表示 pop，3 表示 max）。
接下来的 n 行，每行包含一个操作的具体信息，操作类型和值。

### 输出格式
对于每个 max 操作，输出一行结果，即队列中的最大值。

### 输入样例
```
5 3
1 3
1 5
3
1 7
3
```

### 输出样例
```
5
7
```"""
            # Delete old test cases
            TestCase.query.filter_by(assignment_id=122).delete()
            # Insert new test cases
            new_cases_122 = [
                ('5 3\n1 3\n1 5\n3\n1 7\n3\n', '5\n7'),
                ('5 3\n1 100\n3\n1 200\n3\n2\n', '100\n200'),
                ('6 3\n1 10\n1 20\n3\n2\n3\n2\n', '20\n20'),
                ('2 3\n3\n2\n', '-1'),
                ('6 3\n1 10000\n1 -10000\n3\n2\n3\n2\n', '10000\n-10000')
            ]
            for idx, (inp, out) in enumerate(new_cases_122):
                tc = TestCase(
                    assignment_id=122,
                    input_data=inp,
                    expected_output=out,
                    order_index=idx,
                    is_public=(idx == 0)
                )
                db.session.add(tc)
            print("Fixed assignment 122 successfully.")

        db.session.commit()
        print("All changes committed to database successfully.")

if __name__ == '__main__':
    fix_assignments()
