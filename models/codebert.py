# 可选导入transformers
try:
    from transformers import AutoTokenizer, AutoModel
    HAS_TRANSFORMERS = True
except ImportError:
    print("× transformers库未安装，CodeBERT功能将不可用")
    AutoTokenizer = None
    AutoModel = None
    HAS_TRANSFORMERS = False
import os
import re
import pandas as pd
import numpy as np
import torch
from config import Config


cfg = Config()
all_words = []
# 使用绝对路径加载模型 - 懒加载模式
model_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'CodeBERT_model'))
tokenizer = None
model = None

def load_codebert_model():
    """懒加载CodeBERT模型"""
    global tokenizer, model, model_dir
    
    # 检查transformers库是否可用
    if not HAS_TRANSFORMERS:
        print("× transformers库不可用，无法加载CodeBERT模型")
        return False
    
    if tokenizer is None or model is None:
        try:
            if os.path.exists(model_dir):
                tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
                model = AutoModel.from_pretrained(model_dir, local_files_only=True)
                print("✓ CodeBERT模型加载成功")
            else:
                print(f"× CodeBERT模型目录不存在: {model_dir}")
                print("将使用启发式评估方法")
                return False
        except Exception as e:
            print(f"× CodeBERT模型加载失败: {e}")
            print("将使用启发式评估方法")
            tokenizer = None
            model = None
            return False
    return True


def get_labels(excel_path):
    df = pd.read_excel(excel_path)
    # 提取'代码评分'列的数据
    code_score = df['代码评分']
    # 将'代码评分'数据转换为NumPy数组
    code_scores = np.array(code_score)
    code_labels = torch.nn.functional.one_hot(torch.tensor(code_scores - 1))
    return code_labels.numpy()

def cpp_to_sequence(cpp_code):
    # 使用预训练的BERT分词器将C++代码转换为词元序列
    if not load_codebert_model():
        # 如果模型加载失败，返回零向量
        print("× 无法加载CodeBERT模型，返回零向量")
        return np.zeros((cfg.code_length, cfg.embedding_size))
    
    encoded_input = tokenizer.encode_plus(
        cpp_code,
        add_special_tokens=True,  # 添加 [CLS] 和 [SEP] 标记
        return_tensors='pt',  # 返回 PyTorch 张量
        max_length=cfg.code_length,  # 设置最大序列长度
        padding='max_length',  # 如果序列长度不足，进行填充
        truncation=True  # 如果超出最大长度，进行截断
    )
    input_ids = encoded_input['input_ids']
    attention_mask = encoded_input['attention_mask']
    output = model(input_ids, attention_mask=attention_mask)
    vector = output.last_hidden_state.view(-1).detach().numpy()
    cpp_embedding = vector.reshape(cfg.code_length, cfg.embedding_size)
    return cpp_embedding


def code_sequences(folder_path):
    # 将C++代码转换为词向量序列，并获取对应的唯一标签
    cpp_code_sequences = []
    i = 1
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.cpp'):
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                cpp_code = file.read()
                cpp_code = re.sub(r'//.*?$', '', cpp_code, flags=re.MULTILINE)  # 行注释
                cpp_code = re.sub(r'/\*.*?\*/', '', cpp_code, flags=re.DOTALL)  # 块注释
                cpp_code = re.sub(r'\s+', ' ', cpp_code).strip()
            bert_sequence = cpp_to_sequence(cpp_code)
            print(i, file_path, bert_sequence.shape)
            cpp_code_sequences.append(bert_sequence)
            i = i + 1
    return cpp_code_sequences


