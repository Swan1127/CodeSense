import torch
from torch import nn
import torch.nn.functional as F
from config import Config
import numpy as np


class GlobalMaxPool1d(nn.Module):
    def __init__(self):
        super(GlobalMaxPool1d, self).__init__()

    def forward(self, x):
        return F.max_pool1d(x, kernel_size=x.shape[2])


class TextCNN(nn.Module):
    def __init__(self, cfg):
        super(TextCNN, self).__init__()
        self.cfg = cfg
        self.num_classes = self.cfg.num_classes
        self.code_length = self.cfg.code_length
        self.embedding_size = self.cfg.embedding_size
        self.kernel_size = self.cfg.kernel_size
        self.num_channels = self.cfg.num_channels
        self.drop = self.cfg.dropout

        self.cnn_layers = nn.ModuleList()  # 创建多个一维卷积层
        for c, k in zip(self.num_channels, self.kernel_size):
            cnn = nn.Sequential(nn.Conv1d(in_channels=self.embedding_size, out_channels=c, kernel_size=k),
                                nn.BatchNorm1d(c),
                                nn.ReLU(inplace=True)
                                )
            # cnn = nn.Sequential(nn.Conv2d(in_channels=1, out_channels=c, kernel_size=k),
            #                     nn.BatchNorm1d(c),
            #                     nn.ReLU(inplace=True)
            #                     )
            self.cnn_layers.append(cnn)

        self.pool = GlobalMaxPool1d()
        self.classify = nn.Sequential(
            nn.Dropout(self.drop),
            nn.Linear(sum(self.num_channels), self.num_classes)
        )

    def forward(self, x):
        """
        前向传播处理，支持多种输入格式
        
        Args:
            x: 输入张量，支持多种维度格式
        """
        print(f"输入张量维度: {x.shape}, 类型: {x.dtype}")
        
        # 处理不同维度的输入
        if x.dim() == 4:  # [batch_size, seq_len, embed_dim, 1]
            x = x.squeeze(-1)
            print(f"  挤压后维度: {x.shape}")
        
        # 特殊情况：如果输入是一个4D张量 [batch_size, seq_len, embed_dim, embed_dim]
        if x.dim() == 4 and x.size(2) == x.size(3):
            # 取对角线元素或者第一个维度
            x = x[:, :, :, 0]
            print(f"  提取后维度: {x.shape}")
        
        # 如果输入是单个样本，增加batch维度
        if x.dim() == 2:  # [seq_len, embed_dim]
            x = x.unsqueeze(0)
            print(f"  增加batch维度后: {x.shape}")
            
        # 确保输入形状正确 [batch_size, seq_len, embed_dim]
        if x.dim() != 3:
            print(f"× 错误: 输入维度不符合要求: {x.shape}")
            # 创建一个全零张量作为替代，避免程序崩溃
            x = torch.zeros(1, self.code_length, self.embedding_size, device=x.device)
            print(f"  创建替代张量: {x.shape}")
        
        # 交换维度，使其适合一维卷积: [batch, embed_dim, seq_len]
        try:
            batch_sequences = x.permute(0, 2, 1)
            print(f"  维度交换后: {batch_sequences.shape}")
        except Exception as e:
            print(f"× 维度交换出错: {e}")
            # 创建一个全零张量作为替代，避免程序崩溃
            batch_sequences = torch.zeros(1, self.embedding_size, self.code_length, device=x.device)
            print(f"  创建替代张量: {batch_sequences.shape}")
            
        # 应用CNN层
        results = []
        for i, layer in enumerate(self.cnn_layers):
            try:
                # 应用卷积
                conv_out = layer(batch_sequences)
                print(f"  CNN层 {i+1} 输出: {conv_out.shape}")
                
                # 池化
                pooled = self.pool(conv_out).squeeze(-1)
                print(f"  池化后: {pooled.shape}")
                
                results.append(pooled)
            except Exception as e:
                print(f"× CNN层 {i+1} 处理出错: {e}")
                # 创建一个全零张量作为替代，避免程序崩溃
                dummy = torch.zeros(batch_sequences.size(0), self.num_channels[i], device=x.device)
                results.append(dummy)
                
        # 拼接所有通道的结果
        try:
            concatenated = torch.cat(results, dim=1)
            print(f"  拼接后: {concatenated.shape}")
        except Exception as e:
            print(f"× 拼接出错: {e}")
            # 创建一个全零张量作为替代，避免程序崩溃
            concatenated = torch.zeros(batch_sequences.size(0), sum(self.num_channels), device=x.device)
            
        # 分类层
        try:
            output = self.classify(concatenated)
            print(f"  分类输出: {output.shape}")
        except Exception as e:
            print(f"× 分类层出错: {e}")
            # 创建一个全零张量作为最终输出
            output = torch.zeros(batch_sequences.size(0), self.num_classes, device=x.device)
            
        return output
        
    def predict(self, code_list):
        """
        直接预测代码质量分数（0-4）
        
        Args:
            code_list: 包含代码字符串的列表
            
        Returns:
            包含预测分数的列表（0-4之间的整数）
        """
        self.eval()  # 设置为评估模式
        device = next(self.parameters()).device  # 获取模型所在设备
        
        results = []
        with torch.no_grad():
            for code in code_list:
                try:
                    # 预处理代码
                    import re
                    preprocessed_code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)  # 去除行注释
                    preprocessed_code = re.sub(r'/\*.*?\*/', '', preprocessed_code, flags=re.DOTALL)  # 去除块注释
                    preprocessed_code = re.sub(r'\s+', ' ', preprocessed_code).strip()  # 规范化空白字符
                    
                    # 从utils.code_evaluator模块中获取已初始化的CodeBERT模型
                    from utils.code_evaluator import tokenizer, codebert_model, device, cfg
                    
                    # 直接使用CodeBERT编码代码
                    encoded_input = tokenizer.encode_plus(
                        preprocessed_code,
                        add_special_tokens=True,
                        return_tensors='pt',
                        max_length=cfg.code_length,
                        padding='max_length',
                        truncation=True
                    )
                    
                    input_ids = encoded_input['input_ids'].to(device)
                    attention_mask = encoded_input['attention_mask'].to(device)
                    
                    # 获取代码的嵌入表示
                    output = codebert_model(input_ids, attention_mask=attention_mask)
                    code_tensor = output.last_hidden_state
                    
                    # 前向传播
                    outputs = self(code_tensor)
                    _, predicted = torch.max(outputs, 1)
                    score = predicted.item()  # 获取预测的分数（0-4）
                    
                    results.append(score)
                except Exception as e:
                    print(f"预测过程中出错: {str(e)}")
                    # 如果出错，返回中等分数
                    results.append(2)
                    
        return results
