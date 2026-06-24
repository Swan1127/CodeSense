#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据结构题库与班级初始化脚本
功能：
1. 创建教师账号：刘芳 (t_liufang / liufang123)
2. 创建教学班级：网络2401、网络2402，并指派给刘芳管理
3. 创建默认测试学生：确保班级内非空，避免被系统的空班级清理逻辑误删
4. 导入 51 道数据结构初学者题目，使用自增ID避免编号冲突，按标题排重
"""
import os
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Class, Assignment, TestCase, SystemLog

# 51道初学者数据结构题目设计（移除硬编码的ID，采用数据库自增主键）
ASSIGNMENTS_DATA = [
    {
        "title": "顺序表元素查找",
        "difficulty_level": 1,
        "description": """# 顺序表元素查找

## 题目描述
实现一个顺序表（数组）查找程序。输入一个整数数组和一个目标值，如果目标值存在，输出它在数组中的索引位置（0-based）；如果不存在，则输出 -1。

## 要求
1. 输入数组的大小 n 和目标值 k。
2. 输入 n 个用空格隔开的整数。
3. 输出目标值的索引或 -1。

## 示例
**输入**：
```
5 8
2 5 8 1 9
```
**输出**：
```
2
```
""",
        "cases": [
            ("5 8\n2 5 8 1 9", "2"),
            ("3 10\n1 2 3", "-1")
        ]
    },
    {
        "title": "顺序表删除指定位置元素",
        "difficulty_level": 1,
        "description": """# 顺序表删除指定位置元素

## 题目描述
输入一个数组和一个指定的索引位置，删除该位置上的元素，并输出删除后的新数组。

## 要求
1. 输入包含数组大小 n 和要删除的索引位置 idx。
2. 输入 n 个由空格隔开的整数。
3. 输出删除指定位置后的数组元素，以空格隔开。

## 示例
**输入**：
```
5 2
1 2 3 4 5
```
**输出**：
```
1 2 4 5
```
""",
        "cases": [
            ("5 2\n1 2 3 4 5", "1 2 4 5"),
            ("3 0\n10 20 30", "20 30")
        ]
    },
    {
        "title": "顺序表合并",
        "difficulty_level": 1,
        "description": """# 顺序表合并

## 题目描述
将两个已经升序排列的整数顺序表（数组）合并为一个新的升序数组。

## 要求
1. 输入第一个数组的大小 n1，以及 n1 个已排序的整数。
2. 输入第二个数组的大小 n2，以及 n2 个已排序的整数。
3. 输出合并后的升序数组，元素间用空格分隔。

## 示例
**输入**：
```
3
1 3 5
3
2 4 6
```
**输出**：
```
1 2 3 4 5 6
```
""",
        "cases": [
            ("3\n1 3 5\n3\n2 4 6", "1 2 3 4 5 6"),
            ("2\n10 20\n1\n5", "5 10 20")
        ]
    },
    {
        "title": "顺序表去重",
        "difficulty_level": 1,
        "description": """# 顺序表去重

## 题目描述
输入一个已升序排序的整数顺序表，去除其中重复的元素，输出去重后的数组。

## 要求
1. 输入包含数组大小 n，以及 n 个已排序的整数。
2. 输出去重后的数组元素，以空格分隔。

## 示例
**输入**：
```
6
1 1 2 2 3 4
```
**输出**：
```
1 2 3 4
```
""",
        "cases": [
            ("6\n1 1 2 2 3 4", "1 2 3 4"),
            ("3\n5 5 5", "5")
        ]
    },
    {
        "title": "顺序表奇偶重排",
        "difficulty_level": 2,
        "description": """# 顺序表奇偶重排

## 题目描述
调整顺序表中元素的顺序，将所有的奇数提取到前半部分，所有的偶数提取到后半部分，且分别保持它们在原数组中的相对顺序。

## 要求
1. 输入数组大小 n 级 n 个整数。
2. 输出重排后的数组元素，空格分隔。

## 示例
**输入**：
```
5
1 2 3 4 5
```
**输出**：
```
1 3 5 2 4
```
""",
        "cases": [
            ("5\n1 2 3 4 5", "1 3 5 2 4"),
            ("4\n2 4 6 7", "7 2 4 6")
        ]
    },
    {
        "title": "单链表：求链表的长度",
        "difficulty_level": 1,
        "description": """# 单链表：求链表的长度

## 题目描述
输入一组整数构建一个单链表，然后求出该链表的节点长度并输出。

## 要求
1. 输入链表节点个数 n。
2. 输入 n 个整数以构建链表。
3. 输出链表中的节点总数。

## 示例
**输入**：
```
5
10 20 30 40 50
```
**输出**：
```
5
```
""",
        "cases": [
            ("5\n10 20 30 40 50", "5"),
            ("0\n", "0")
        ]
    },
    {
        "title": "单链表：向指定位置插入节点",
        "difficulty_level": 2,
        "description": """# 单链表：向指定位置插入节点

## 题目描述
在单链表的指定索引位置（0-based）插入一个新的值，然后打印整个链表。如果位置不合法（小于 0 或大于当前链表长度），则不插入，输出 `Invalid`。

## 要求
1. 输入链表初始大小 n，及 n 个初始节点值。
2. 输入插入位置的索引 idx 以及要插入的整数值 val。
3. 输出插入新节点后的链表元素，或输出 `Invalid`。

## 示例
**输入**：
```
3
1 2 3
1 99
```
**输出**：
```
1 99 2 3
```
""",
        "cases": [
            ("3\n1 2 3\n1 99", "1 99 2 3"),
            ("3\n1 2 3\n4 99", "Invalid")
        ]
    },
    {
        "title": "单链表：删除指定值的节点",
        "difficulty_level": 1,
        "description": """# 单链表：删除指定值的节点

## 题目描述
在一个单链表中，删除所有值等于给定 `val` 的节点，并打印删除后的链表。

## 要求
1. 输入包含节点个数 n，以及 n 个整数。
2. 输入待删除的目标值 val。
3. 输出删除操作后的链表元素，以空格隔开。若为空链表，输出空行。

## 示例
**输入**：
```
5
1 2 3 2 4
2
```
**输出**：
```
1 3 4
```
""",
        "cases": [
            ("5\n1 2 3 2 4\n2", "1 3 4"),
            ("3\n2 2 2\n2", "")
        ]
    },
    {
        "title": "单链表：查找倒数第 K 个节点",
        "difficulty_level": 2,
        "description": """# 单链表：查找倒数第 K 个节点

## 题目描述
输入一个单链表，输出它的倒数第 k 个节点的值。如果 k 不合法（如 k <= 0 或 k 大于链表长度），则输出 -1。

## 要求
1. 输入链表总长度 n 以及倒数位置 k。
2. 输入 n 个整数。
3. 输出对应的倒数第 k 个节点的值，若不合法输出 -1。

## 示例
**输入**：
```
5 2
1 2 3 4 5
```
**输出**：
```
4
```
""",
        "cases": [
            ("5 2\n1 2 3 4 5", "4"),
            ("3 4\n1 2 3", "-1")
        ]
    },
    {
        "title": "单链表：合并两个有序链表",
        "difficulty_level": 2,
        "description": """# 单链表：合并两个有序链表

## 题目描述
将两个升序排列的单链表合并为一个新的升序排列单链表。

## 要求
1. 输入第一个链表的长度 n1，以及 n1 个升序排列的整数。
2. 输入第二个链表的长度 n2，以及 n2 个升序排列的整数。
3. 输出合并后的升序链表，以空格隔开。

## 示例
**输入**：
```
3
1 3 5
3
2 4 6
```
**输出**：
```
1 2 3 4 5 6
```
""",
        "cases": [
            ("3\n1 3 5\n3\n2 4 6", "1 2 3 4 5 6"),
            ("1\n5\n0\n", "5")
        ]
    },
    {
        "title": "单链表：反转单链表",
        "difficulty_level": 2,
        "description": """# 单链表：反转单链表

## 题目描述
实现单链表的就地反转算法，将链表从 `1->2->3` 变为 `3->2->1` 并打印。

## 要求
1. 输入链表长度 n。
2. 输入 n 个整数。
3. 输出反转后的链表，空格分隔。

## 示例
**输入**：
```
5
1 2 3 4 5
```
**输出**：
```
5 4 3 2 1
```
""",
        "cases": [
            ("5\n1 2 3 4 5", "5 4 3 2 1"),
            ("1\n10", "10")
        ]
    },
    {
        "title": "双向链表：头插法构建与打印",
        "difficulty_level": 2,
        "description": """# 双向链表：头插法构建与打印

## 题目描述
使用头插法（每次都在链表头部插入新节点）构建一个双向链表。为验证双向链表的左右指针链接是否正确，请正向打印一次，再反向打印一次。

## 要求
1. 输入节点数量 n。
2. 输入 n 个依次执行头插的整数。
3. 第一行正向输出链表。
4. 第二行反向输出链表。

## 示例
**输入**：
```
3
10 20 30
```
**输出**：
```
30 20 10
10 20 30
```
""",
        "cases": [
            ("3\n10 20 30", "30 20 10\n10 20 30"),
            ("1\n5", "5\n5")
        ]
    },
    {
        "title": "双向链表：删除指定节点",
        "difficulty_level": 2,
        "description": """# 双向链表：删除指定节点

## 题目描述
构建一个双向链表，并删除其中指定位置 idx (0-based) 处的节点，然后输出删除后的链表元素。

## 要求
1. 输入包含链表节点数 n 以及待删除的索引 idx。
2. 输入 n 个整数表示链表初始元素。
3. 输出删除操作后的正向遍历结果。

## 示例
**输入**：
```
4 2
1 2 3 4
```
**输出**：
```
1 2 4
```
""",
        "cases": [
            ("4 2\n1 2 3 4", "1 2 4"),
            ("1 0\n100", "")
        ]
    },
    {
        "title": "循环单链表：约瑟夫环简化版",
        "difficulty_level": 3,
        "description": """# 循环单链表：约瑟夫环简化版

## 题目描述
有 n 个人围成一圈，顺序排号 1 到 n。从第 1 个人开始报数（从 1 到 m），凡报到 m 的人退出圈子。使用循环单链表模拟此过程，问最后留下的是原来第几号的那个人？

## 要求
1. 输入总人数 n 和报数间隔 m。
2. 输出最后一人的编号。

## 示例
**输入**：
```
5 3
```
**输出**：
```
4
```
""",
        "cases": [
            ("5 3", "4"),
            ("8 4", "6")
        ]
    },
    {
        "title": "顺序栈：判断空与满",
        "difficulty_level": 2,
        "description": """# 顺序栈：基本状态判断

## 题目描述
设计一个固定大小为 5 的顺序栈。输入一系列操作：`push x`（入栈）、`pop`（出栈）。在每次操作后，若栈满输出 `Full`，若栈空输出 `Empty`，否则输出栈顶元素。如果出现非法操作（空栈 pop 或 满栈 push），则该步输出 `Error`。

## 要求
1. 输入包含操作步数 n。
2. 接下来 n 行，每行为 `push x` 或 `pop`。
3. 针对每一步指令，输出对应的结果或状态。

## 示例
**输入**：
```
3
push 10
push 20
pop
```
**输出**：
```
10
20
10
```
""",
        "cases": [
            ("3\npush 10\npush 20\npop", "10\n20\n10"),
            ("2\npop\npush 5", "Error\n5")
        ]
    },
    {
        "title": "栈的应用：十进制转二进制",
        "difficulty_level": 1,
        "description": """# 栈的应用：十进制转二进制

## 题目描述
利用栈的后进先出（LIFO）特性，将输入的非负十进制整数转换为二进制数并输出。

## 要求
1. 输入一个十进制非负整数 n。
2. 输出其对应的二进制字符串。

## 示例
**输入**：
```
10
```
**输出**：
```
1010
```
""",
        "cases": [
            ("10", "1010"),
            ("0", "0"),
            ("255", "11111111")
        ]
    },
    {
        "title": "栈的应用：括号匹配",
        "difficulty_level": 2,
        "description": """# 栈的应用：括号匹配

## 题目描述
输入一个仅包含括号字符 `'('`, `')'`, `'['`, `']'`, `'{'`, `'}'` 的字符串，利用栈结构判断括号匹配是否合法。

## 要求
1. 输入一串括号字符串。
2. 若合法输出 `Yes`；否则输出 `No`。

## 示例
**输入**：
```
{[()]}
```
**输出**：
```
Yes
```
""",
        "cases": [
            ("{[()]}", "Yes"),
            ("([)]", "No"),
            ("(", "No")
        ]
    },
    {
        "title": "栈的应用：逆波兰表达式求值",
        "difficulty_level": 3,
        "description": """# 栈的应用：逆波兰表达式求值

## 题目描述
利用栈计算后缀表达式（逆波兰表达式）的值。运算符仅包含 `+`, `-`, `*`, `/`，操作数均为整数。除法为整除，且题目保证除数不为0。

## 要求
1. 输入一行以空格隔开的后缀表达式。
2. 输出计算得出的整数值。

## 示例
**输入**：
```
3 4 + 5 *
```
**输出**：
```
35
```
""",
        "cases": [
            ("3 4 + 5 *", "35"),
            ("12 3 /", "4")
        ]
    },
    {
        "title": "循环队列：基本操作",
        "difficulty_level": 2,
        "description": """# 循环队列：基本操作

## 题目描述
设计一个固定大小为 3 的循环队列。实现 `push x` 和 `pop` 操作。每次操作后输出队列的当前所有元素（从队头到队尾，以空格分隔）。若队列为空输出 `Empty`。若满队无法 push 或空队无法 pop，则对应步输出 `Error` 且队列保持原有状态。

## 要求
1. 输入包含操作指令数 n。
2. 接下来 n 行输入操作指令。
3. 输出每一步执行后队列的存储内容或错误状态。

## 示例
**输入**：
```
5
push 1
push 2
pop
push 3
push 4
```
**输出**：
```
1
1 2
2
2 3
Error
```
""",
        "cases": [
            ("5\npush 1\npush 2\npop\npush 3\npush 4", "1\n1 2\n2\n2 3\nError"),
            ("2\npop\npush 10", "Error\n10")
        ]
    },
    {
        "title": "队列应用：舞伴配对",
        "difficulty_level": 2,
        "description": """# 队列应用：舞伴配对

## 题目描述
男士和女士在跳舞前各排成一个队伍。跳舞开始时，依次从男队和女队的队头各出一人配成舞伴。如果两队人数不等，多余的人员在队尾等待下一轮。输出成功配对的舞伴，以及男队 and 女队各自剩余的人数。

## 要求
1. 输入男士人数 m 和女士人数 f。
2. 输入男士姓名列表（空格隔开）。
3. 输入女士姓名列表（空格隔开）。
4. 输出配对结果 `'M_name - F_name'`，并在最后一行输出两个剩余人数。

## 示例
**输入**：
```
3 2
Bob Tom Jack
Alice Mary
```
**输出**：
```
Bob - Alice
Tom - Mary
1 0
```
""",
        "cases": [
            ("3 2\nBob Tom Jack\nAlice Mary", "Bob - Alice\nTom - Mary\n1 0"),
            ("1 2\nAlan\nBetty Clara", "Alan - Betty\n0 1")
        ]
    },
    {
        "title": "双端队列：双向出入队",
        "difficulty_level": 2,
        "description": """# 双端队列：双向出入队

## 题目描述
实现一个双端队列（Deque），支持以下四种操作：
1. `push_front x`: 队头插入
2. `push_back x`: 队尾插入
3. `pop_front`: 弹出队头并输出
4. `pop_back`: 弹出队尾并输出
若队列为空时进行 pop，输出 `Empty`。

## 要求
1. 输入包含操作数 n。
2. 接下来 n 行指令。
3. 针对每次 pop 操作，输出其值或 `Empty`。

## 示例
**输入**：
```
5
push_back 10
push_front 20
pop_back
pop_back
pop_front
```
**输出**：
```
10
20
Empty
```
""",
        "cases": [
            ("5\npush_back 10\npush_front 20\npop_back\npop_back\npop_front", "10\n20\nEmpty"),
            ("1\npop_front", "Empty")
        ]
    },
    {
        "title": "串的逆置",
        "difficulty_level": 1,
        "description": """# 串的逆置

## 题目描述
输入一个字符串，将其就地逆置，并输出逆置后的字符串。

## 要求
1. 输入一行字符串.
2. 输出逆序后的串。

## 示例
**输入**：
```
hello
```
**输出**：
```
olleh
```
""",
        "cases": [
            ("hello", "olleh"),
            ("a", "a")
        ]
    },
    {
        "title": "朴素模式匹配",
        "difficulty_level": 2,
        "description": """# 朴素模式匹配

## 题目描述
实现朴素的字符串模式匹配算法（BF算法）。输入主串 S 和模式串 T，输出 T 在 S 中第一次出现的位置（0-based 索引）。如果不存在，输出 -1。

## 要求
1. 输入第一行为主串 S。
2. 输入第二行为模式串 T。
3. 输出匹配的起始索引值或 -1。

## 示例
**输入**：
```
abcdefg
cde
```
**输出**：
```
2
```
""",
        "cases": [
            ("abcdefg\ncde", "2"),
            ("hello\nworld", "-1")
        ]
    },
    {
        "title": "字符串最长公共前缀",
        "difficulty_level": 2,
        "description": """# 字符串最长公共前缀

## 题目描述
编写程序，查找一组字符串中的最长公共前缀。若不存在公共前缀，输出空行。

## 要求
1. 输入包含字符串数量 n。
2. 接下来 n 行，每行输入一个字符串.
3. 输出它们的最长公共前缀。

## 示例
**输入**：
```
3
flower
flow
flight
```
**输出**：
```
fl
```
""",
        "cases": [
            ("3\nflower\nflow\nflight", "fl"),
            ("2\ndog\nracecar", "")
        ]
    },
    {
        "title": "二叉树：计算节点个数",
        "difficulty_level": 2,
        "description": """# 二叉树：计算节点个数

## 题目描述
给定一棵完全二叉树的层序遍历序列，其中数字 `0` 表示空节点。请计算其中所有非空节点的总个数。

## 要求
1. 第一行输入序列长度 n。
2. 第二行输入 n 个以空格隔开的整数表示层序序列。
3. 输出非空节点总数。

## 示例
**输入**：
```
5
1 2 3 0 4
```
**输出**：
```
4
```
""",
        "cases": [
            ("5\n1 2 3 0 4", "4"),
            ("1\n0", "0")
        ]
    },
    {
        "title": "二叉树：计算叶子节点个数",
        "difficulty_level": 2,
        "description": """# 二叉树：计算叶子节点个数

## 题目描述
给定一棵完全二叉树的层序遍历表示（0表示空节点），求这棵二叉树中所有叶子节点（即左右子节点均为空的节点）的个数。

## 示例
**输入**：
```
5
1 2 3 0 4
```
**输出**：
```
2
```
""",
        "cases": [
            ("5\n1 2 3 0 4", "2"),
            ("3\n1 0 0", "1")
        ]
    },
    {
        "title": "二叉树：求树的深度",
        "difficulty_level": 2,
        "description": """# 二叉树：求树的深度

## 题目描述
根据输入的一棵完全二叉树层序遍历序列（0表示空节点），计算该二叉树的最大深度（高度）。

## 示例
**输入**：
```
5
1 2 3 0 4
```
**输出**：
```
3
```
""",
        "cases": [
            ("5\n1 2 3 0 4", "3"),
            ("3\n1 0 0", "1")
        ]
    },
    {
        "title": "二叉树：判断两棵树是否相同",
        "difficulty_level": 2,
        "description": """# 二叉树：判断两棵树是否相同

## 题目描述
给定两棵树的层序遍历（0表示空），判断它们是否结构和权值完全一样。相同输出 `Same`，否则输出 `Different`。

## 示例
**输入**：
```
3
1 2 3
3
1 2 3
```
**输出**：
```
Same
```
""",
        "cases": [
            ("3\n1 2 3\n3\n1 2 3", "Same"),
            ("3\n1 2 3\n3\n1 3 2", "Different")
        ]
    },
    {
        "title": "二叉树：重建并输出中序遍历",
        "difficulty_level": 3,
        "description": """# 二叉树：重建并输出中序遍历

## 题目描述
输入一棵二叉树的先序遍历字符串（字符 `#` 表示空节点），请输出该树的中序遍历序列，节点字符间用空格分隔。

## 示例
**输入**：
```
AB##C##
```
**输出**：
```
B A C
```
""",
        "cases": [
            ("AB##C##", "B A C"),
            ("A##", "A")
        ]
    },
    {
        "title": "二叉树：翻转二叉树",
        "difficulty_level": 3,
        "description": """# 二叉树：翻转二叉树

## 题目描述
翻转一棵二叉树（即交换每个节点的左右子树）。输入一棵树的先序遍历（以 `#` 表示空），输出翻转后整棵树的先序遍历字符串。

## 示例
**输入**：
```
AB##C##
```
**输出**：
```
AC##B##
```
""",
        "cases": [
            ("AB##C##", "AC##B##"),
            ("A##", "A##")
        ]
    },
    {
        "title": "二叉搜索树：插入节点",
        "difficulty_level": 2,
        "description": """# 二叉搜索树：插入节点

## 题目描述
给定一组整数，依次插入到初始为空的二叉搜索树（BST）中。在最后输出这棵树的中序遍历结果（中序遍历BST会得到一个递增的有序序列）。

## 示例
**输入**：
```
5
4 2 5 1 3
```
**输出**：
```
1 2 3 4 5
```
""",
        "cases": [
            ("5\n4 2 5 1 3", "1 2 3 4 5"),
            ("3\n10 5 15", "5 10 15")
        ]
    },
    {
        "title": "二叉搜索树：查找元素",
        "difficulty_level": 2,
        "description": """# 二叉搜索树：查找元素

## 题目描述
构建一棵二叉搜索树（BST），并查找指定的数字是否存在。如果找到输出 `Found`，没找到输出 `NotFound`。

## 示例
**输入**：
```
5 3
4 2 5 1 3
```
**输出**：
```
Found
```
""",
        "cases": [
            ("5 3\n4 2 5 1 3", "Found"),
            ("3 10\n1 2 3", "NotFound")
        ]
    },
    {
        "title": "二叉搜索树：极值查找",
        "difficulty_level": 2,
        "description": """# 二叉搜索树：极值查找

## 题目描述
构建一棵二叉搜索树，并输出树中的最小值和最大值。

## 示例
**输入**：
```
5
8 3 10 1 6
```
**输出**：
```
1 10
```
""",
        "cases": [
            ("5\n8 3 10 1 6", "1 10"),
            ("1\n50", "50 50")
        ]
    },
    {
        "title": "哈夫曼树：计算带权路径长度 WPL",
        "difficulty_level": 3,
        "description": """# 哈夫曼树：计算带权路径长度 WPL

## 题目描述
给定 n 个叶子节点的权值，请构建哈夫曼树，并计算它的带权路径长度（WPL）。

## 提示
可通过最小堆（优先队列）实现。每次取出两个权值最小的节点合成父节点，父节点权值为子节点权值之和，再将父节点重新放回堆中，累加每次合成的新权值即为 WPL。

## 示例
**输入**：
```
4
2 4 5 3
```
**输出**：
```
28
```
""",
        "cases": [
            ("4\n2 4 5 3", "28"),
            ("3\n1 2 3", "9")
        ]
    },
    {
        "title": "图：邻接矩阵中顶点的度数",
        "difficulty_level": 2,
        "description": """# 图：邻接矩阵中顶点的度数

## 题目描述
给定一个无向图的邻接矩阵表示，计算并输出指定顶点 v (0-based) 的度数。

## 示例
**输入**：
```
4 1
0 1 1 0
1 0 1 1
1 1 0 0
0 1 0 0
```
**输出**：
```
3
```
""",
        "cases": [
            ("4 1\n0 1 1 0\n1 0 1 1\n1 1 0 0\n0 1 0 0", "3"),
            ("3 0\n0 0 0\n0 0 1\n0 1 0", "0")
        ]
    },
    {
        "title": "图：有向图顶点的度数",
        "difficulty_level": 2,
        "description": """# 图：有向图顶点的度数

## 题目描述
给定一个有向图（输入格式：顶点数 n、边数 e、目标顶点 v，随后输入 e 行表示弧的 src 到 dest 关系），输出目标顶点的出度和入度，以空格隔开。

## 示例
**输入**：
```
4 4 1
0 1
1 2
1 3
2 1
```
**输出**：
```
2 2
```
""",
        "cases": [
            ("4 4 1\n0 1\n1 2\n1 3\n2 1", "2 2"),
            ("3 2 0\n1 2\n2 1", "0 0")
        ]
    },
    {
        "title": "图：判断路径是否存在",
        "difficulty_level": 2,
        "description": """# 图：判断路径是否存在

## 题目描述
给定一个无向图（顶点数 n、边数 e、起点 s、终点 d），判断从 s 到 d 是否存在通路。存在输出 `Yes`，否则输出 `No`。

## 示例
**输入**：
```
4 3 0 3
0 1
1 2
2 3
```
**输出**：
```
Yes
```
""",
        "cases": [
            ("4 3 0 3\n0 1\n1 2\n2 3", "Yes"),
            ("4 2 0 3\n0 1\n2 3", "No")
        ]
    },
    {
        "title": "哈希表：线性探测法查找",
        "difficulty_level": 2,
        "description": """# 哈希表：线性探测法查找

## 题目描述
使用哈希函数 H(key) = key % 11，大小为 11。采用线性探测再散列解决冲突。输入关键字个数 n 依次插入，最后输入待查找关键字，输出其在哈希表中的索引位置。若不存在输出 -1。

## 示例
**输入**：
```
4
12 23 34 1
23
```
**输出**：
```
2
```
""",
        "cases": [
            ("4\n12 23 34 1\n23", "2"),
            ("3\n5 16 27\n8", "-1")
        ]
    },
    {
        "title": "折半插入排序",
        "difficulty_level": 2,
        "description": """# 折半插入排序

## 题目描述
实现折半插入排序算法，对输入的整数序列进行递增排序。

## 示例
**输入**：
```
5
5 2 4 1 3
```
**输出**：
```
1 2 3 4 5
```
""",
        "cases": [
            ("5\n5 2 4 1 3", "1 2 3 4 5"),
            ("3\n9 9 1", "1 9 9")
        ]
    },
    {
        "title": "希尔排序",
        "difficulty_level": 2,
        "description": """# 希尔排序

## 题目描述
实现希尔排序算法对整数序列进行升序排序。初始步长设为 n/2，每次步长折半，直到步长为 1。

## 示例
**输入**：
```
6
9 8 3 7 5 6
```
**输出**：
```
3 5 6 7 8 9
```
""",
        "cases": [
            ("6\n9 8 3 7 5 6", "3 5 6 7 8 9"),
            ("2\n2 1", "1 2")
        ]
    },
    {
        "title": "快速排序：划分函数",
        "difficulty_level": 3,
        "description": """# 快速排序：划分函数

## 题目描述
实现快速排序中的 Partition（划分）操作。规定使用数组的最后一个元素做基准（pivot），使用 Lomuto 划分方式。最终输出划分后基准的索引。

```cpp
int partition(int arr[], int low, int high) {
    int pivot = arr[high];
    int i = low - 1;
    for (int j = low; j < high; j++) {
        if (arr[j] <= pivot) {
            i++;
            swap(arr[i], arr[j]);
        }
    }
    swap(arr[i + 1], arr[high]);
    return i + 1;
}
```

## 示例
**输入**：
```
5
2 8 7 1 5
```
**输出**：
```
1
```
""",
        "cases": [
            ("5\n2 8 7 1 5", "1"),
            ("3\n3 2 1", "0")
        ]
    },
    {
        "title": "堆排序：最大堆调整",
        "difficulty_level": 3,
        "description": """# 堆排序：最大堆调整

## 题目描述
给定一个表示完全二叉树的数组以及需调整的节点索引 i。请对以索引 i 为根的子树进行最大堆调整（Heapify），并输出调整后的数组序列。

## 示例
**输入**：
```
5 0
4 10 3 5 1
```
**输出**：
```
10 5 3 4 1
```
""",
        "cases": [
            ("5 0\n4 10 3 5 1", "10 5 3 4 1"),
            ("3 0\n1 3 2", "3 1 2")
        ]
    },
    {
        "title": "冒泡排序优化版",
        "difficulty_level": 2,
        "description": """# 冒泡排序优化版

## 题目描述
在冒泡排序中，若某一趟排序没有发生交换，则说明已排序好，应提前终止。请输出优化后的冒泡排序外层循环的总执行次数。

## 示例
**输入**：
```
5
1 2 3 5 4
```
**输出**：
```
2
```
""",
        "cases": [
            ("5\n1 2 3 5 4", "2"),
            ("5\n1 2 3 4 5", "1")
        ]
    },
    {
        "title": "计数排序",
        "difficulty_level": 2,
        "description": """# 计数排序

## 题目描述
实现计数排序算法对非负整数数组进行升序排序。假设数组中所有元素的值均在 0 到 100 之间。

## 示例
**输入**：
```
5
4 2 2 8 3
```
**输出**：
```
2 2 3 4 8
```
""",
        "cases": [
            ("5\n4 2 2 8 3", "2 2 3 4 8"),
            ("3\n0 100 50", "0 50 100")
        ]
    },
    {
        "title": "顺序表查找最大最小元素",
        "difficulty_level": 1,
        "description": """# 顺序表查找最大最小元素

## 题目描述
在一个包含 n 个整数的数组中，找出最小值和最大值并在一行输出，以空格分隔。

## 示例
**输入**：
```
5
3 9 2 8 5
```
**输出**：
```
2 9
```
""",
        "cases": [
            ("5\n3 9 2 8 5", "2 9"),
            ("2\n10 -5", "-5 10")
        ]
    },
    {
        "title": "串：回文判断",
        "difficulty_level": 1,
        "description": """# 串：回文判断

## 题目描述
输入一个字符串，判断它是否是回文（忽略大小写，且仅考虑字母及数字字符）。是输出 `Yes`，否则输出 `No`。

## 示例
**输入**：
```
A man, a plan, a canal: Panama
```
**输出**：
```
Yes
```
""",
        "cases": [
            ("A man, a plan, a canal: Panama", "Yes"),
            ("hello", "No")
        ]
    },
    {
        "title": "单链表：奇偶位置节点重排",
        "difficulty_level": 3,
        "description": """# 单链表：奇偶位置节点重排

## 题目描述
给定一个单链表，把所有的奇数节点（指排在第1, 3, 5...个位置的节点，非节点值奇偶）和偶数节点分别排在一起，奇数在前，偶数在后，并保持原有的相对顺序，最后输出重排后的链表。

## 示例
**输入**：
```
5
1 2 3 4 5
```
**输出**：
```
1 3 5 2 4
```
""",
        "cases": [
            ("5\n1 2 3 4 5", "1 3 5 2 4"),
            ("4\n10 20 30 40", "10 30 20 40")
        ]
    },
    {
        "title": "二叉搜索树：验证二叉搜索树",
        "difficulty_level": 3,
        "description": """# 二叉搜索树：验证二叉搜索树

## 题目描述
根据输入的一棵完全二叉树的层序遍历序列（0表示空节点），判断该二叉树是否为合法的二叉搜索树（BST）。合法输出 `Yes`，否则输出 `No`。

## 示例
**输入**：
```
3
2 1 3
```
**输出**：
```
Yes
```
""",
        "cases": [
            ("3\n2 1 3", "Yes"),
            ("3\n1 2 3", "No")
        ]
    },
    {
        "title": "图：无向图的邻接表与 DFS",
        "difficulty_level": 3,
        "description": """# 图：无向图的邻接表与 DFS

## 题目描述
给定一个无向图（顶点数 n、边数 e，接着输入 e 行边关系），实现它的邻接表表示，并输出从顶点 0 开始的深度优先搜索（DFS）遍历序列。多个邻接点可选时，规定按节点索引从小到大顺序遍历。

## 示例
**输入**：
```
4 4
0 1
0 2
1 3
2 3
```
**输出**：
```
0 1 3 2
```
""",
        "cases": [
            ("4 4\n0 1\n0 2\n1 3\n2 3", "0 1 3 2"),
            ("3 2\n0 1\n1 2", "0 1 2")
        ]
    },
    {
        "title": "图：无向图的邻接矩阵与 BFS",
        "difficulty_level": 3,
        "description": """# 图：无向图的邻接矩阵与 BFS

## 题目描述
给定一个无向图（顶点数 n、边数 e，接着输入 e 行边关系），实现它的邻接矩阵表示，并输出从顶点 0 开始的广度优先搜索（BFS）遍历序列。邻接点按索引由小到大顺序入队。

## 示例
**输入**：
```
4 4
0 1
0 2
1 3
2 3
```
**输出**：
```
0 1 2 3
```
""",
        "cases": [
            ("4 4\n0 1\n0 2\n1 3\n2 3", "0 1 2 3"),
            ("3 2\n0 1\n0 2", "0 1 2")
        ]
    },
    {
        "title": "哈希表：拉链法哈希构建",
        "difficulty_level": 3,
        "description": """# 哈希表：拉链法哈希构建

## 题目描述
实现一个大小为 7 的哈希表，哈希函数为 H(key) = key % 7。采用拉链法解决冲突。请依次插入 n 个正整数，并按索引 0 到 6 的顺序输出每个哈希槽中的链表元素。如果某个槽为空，则该行输出 `Empty`。

## 示例
**输入**：
```
4
7 14 8 9
```
**输出**：
```
7 14
8
9
Empty
Empty
Empty
Empty
```
""",
        "cases": [
            ("4\n7 14 8 9", "7 14\n8\n9\nEmpty\nEmpty\nEmpty\nEmpty"),
            ("3\n0 7 1", "0 7\n1\nEmpty\nEmpty\nEmpty\nEmpty\nEmpty")
        ]
    }
]


def run_setup():
    # 自动识别环境并初始化 App 实例
    config_name = os.getenv('FLASK_CONFIG') or 'development'
    app = create_app(config_name)
    
    with app.app_context():
        print(f"[*] 正在使用配置: {config_name}，数据库地址: {db.engine.url}")
        
        # 1. 创建教师
        teacher = User.query.filter_by(student_id='t_liufang').first()
        if not teacher:
            teacher = User(
                student_id='t_liufang',
                username='liufang',
                password_hash=generate_password_hash('liufang123'),
                usertype='教师',
                full_name='刘芳',
                submit_count=0,
                user_ascore=0.0,
            )
            db.session.add(teacher)
            db.session.commit()
            print("[+] 教师账号创建成功 (t_liufang / liufang123)")
        else:
            print("[i] 教师账号 '刘芳' 已存在，跳过创建")

        # 2. 创建班级并指派给刘芳
        class_names = ['网络2401', '网络2402']
        class_objs = {}
        for name in class_names:
            cls = Class.query.filter_by(name=name).first()
            if not cls:
                cls = Class(
                    name=name,
                    grade='2024',
                    major='网络工程',
                    teacher_id=teacher.student_id
                )
                db.session.add(cls)
                print(f"[+] 班级 {name} 创建成功，由教师 '{teacher.full_name}' 管理")
            else:
                cls.teacher_id = teacher.student_id
                print(f"[i] 班级 {name} 已存在，已更新其管理教师为 '{teacher.full_name}'")
            class_objs[name] = cls
        db.session.commit()

        # 3. 从外部名册文件加载学生账号（不在代码中存储个人信息）
        # 支持两种方式：
        #   方式A: 提供 Excel 名册文件路径（推荐）
        #   方式B: 提供 CSV 名册文件路径
        #
        # Excel 格式要求（从第6行开始，前5行为表头）：
        #   列顺序: 序号 | 学号 | 姓名 | 班级 | ...（后续列忽略）
        #
        # CSV 格式要求（有表头行）：
        #   student_id,name,class_name
        #   243401040101,张某某,网络2401
        #
        # 使用方法（在项目根目录放置名册文件后运行）：
        #   python scripts/setup_ds_course.py --roster 名册文件.xlsx
        #   python scripts/setup_ds_course.py --roster 名册文件.csv
        #
        # ⚠️  隐私说明：名册文件包含学生个人信息，请勿提交到 git 仓库。
        #              已在 .gitignore 中添加常见名册文件名的屏蔽规则。

        import argparse
        import sys

        # 解析命令行参数
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--roster', type=str, default=None)
        args, _ = parser.parse_known_args()

        students_info = []

        if args.roster:
            roster_path = args.roster
            if not os.path.exists(roster_path):
                print(f"[✗] 名册文件不存在: {roster_path}")
                sys.exit(1)

            if roster_path.endswith('.xlsx') or roster_path.endswith('.xls'):
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(roster_path)
                    ws = wb.active
                    for row in ws.iter_rows(min_row=6, values_only=True):
                        seq, student_id, name, cls = row[0], row[1], row[2], row[3]
                        if not (student_id and name and cls):
                            continue
                        sid = str(int(student_id)) if isinstance(student_id, float) else str(student_id).strip()
                        sname = str(name).strip()
                        scls = str(cls).strip()
                        if sid and sname and scls and sname != '姓名':
                            students_info.append({'student_id': sid, 'full_name': sname, 'class_name': scls})
                    print(f"[✓] 从 Excel 名册读取到 {len(students_info)} 名学生")
                except ImportError:
                    print("[✗] 需要安装 openpyxl: pip install openpyxl")
                    sys.exit(1)

            elif roster_path.endswith('.csv'):
                import csv
                with open(roster_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        students_info.append({
                            'student_id': row['student_id'].strip(),
                            'full_name': row['name'].strip(),
                            'class_name': row['class_name'].strip()
                        })
                print(f"[✓] 从 CSV 名册读取到 {len(students_info)} 名学生")
            else:
                print(f"[✗] 不支持的文件格式，请使用 .xlsx 或 .csv")
                sys.exit(1)
        else:
            print("[i] 未指定名册文件，跳过学生账号注册步骤")
            print("    如需注册学生，请运行: python scripts/setup_ds_course.py --roster 名册.xlsx")

        # 批量注册学生账号（用户名=学号，密码=学号，幂等执行）
        created_count = 0
        updated_count = 0
        for si in students_info:
            # 确保班级存在（若名册中有新班级则自动创建）
            cls = class_objs.get(si['class_name'])
            if not cls:
                cls = Class.query.filter_by(name=si['class_name']).first()
                if not cls:
                    cls = Class(
                        name=si['class_name'],
                        grade='2024',
                        major='网络工程',
                        teacher_id=teacher.student_id
                    )
                    db.session.add(cls)
                    db.session.commit()
                    print(f"[+] 自动创建班级: {si['class_name']}")
                class_objs[si['class_name']] = cls

            stu = User.query.filter_by(student_id=si['student_id']).first()
            if not stu:
                stu = User(
                    student_id=si['student_id'],
                    username=si['student_id'],
                    password_hash=generate_password_hash(si['student_id']),
                    usertype='学生',
                    full_name=si['full_name'],
                    class_name=si['class_name'],
                    class_id=cls.id,
                    submit_count=0,
                    user_ascore=0.0
                )
                db.session.add(stu)
                created_count += 1
                print(f"[+] 注册学生: {si['full_name']} ({si['student_id']}) → {si['class_name']}")
            else:
                stu.class_name = si['class_name']
                stu.class_id = cls.id
                stu.full_name = si['full_name']
                updated_count += 1
        db.session.commit()
        if students_info:
            print(f"\n[*] 学生账号：新建 {created_count} 个，更新 {updated_count} 个，共 {len(students_info)} 人")


        # 4. 批量添加作业题目
        assignment_count = 0
        test_case_count = 0
        
        for item in ASSIGNMENTS_DATA:
            # 用标题做排重检查，确保在任何已有库的情况下都能安全执行
            existing = Assignment.query.filter_by(title=item['title']).first()
            if existing:
                print(f"[i] 作业 '{item['title']}' 已存在，跳过")
                continue
            
            # 创建新作业，不指定 ID，使用数据库自增主键
            new_assign = Assignment(
                title=item['title'],
                description=item['description'],
                total_score=100,
                average_score=0.0,
                count=0,
                created_time=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=60),
                target_classes=','.join(class_names),
                difficulty_level=item['difficulty_level'],
                creator_id=teacher.student_id
            )
            db.session.add(new_assign)
            db.session.commit() # 提前提交让数据库为 new_assign.id 自动赋值并回填，供 TestCase 外键关联
            assignment_count += 1
            
            # 创建测试用例
            for idx, (inp, out) in enumerate(item['cases']):
                case = TestCase(
                    assignment_id=new_assign.id,
                    input_data=inp,
                    expected_output=out,
                    order_index=idx,
                    is_public=(idx == 0) # 第一个用例公开
                )
                db.session.add(case)
                test_case_count += 1
            db.session.commit()
            
            # 记录系统日志
            SystemLog.add_log(
                log_type='添加作业',
                content=f'初始化脚本导入了新作业：{new_assign.title} (ID: {new_assign.id})',
                user_id='admin_001',
                icon='bi bi-file-earmark-plus'
            )
            print(f"[+] 成功添加数据结构作业: {new_assign.title} (ID: {new_assign.id})")
            
        # 同步班级统计数据
        Class.sync_from_users()
        print(f"\n[*] 任务全部完成：")
        print(f"    - 新增作业题目：{assignment_count} 个")
        print(f"    - 新增测试用例：{test_case_count} 个")


if __name__ == "__main__":
    run_setup()
