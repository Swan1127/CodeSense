import time
import os
import secrets


class Config(object):
    """
    基础配置类
    所有敏感信息都从环境变量中读取，不提供硬编码的默认值
    """

    def __init__(self):
        # 获取项目根目录路径
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Gpu
        self.use_gpu = False
        self.use_multi_gpu = False
        self.device_list = "0"  # id list of gpus used for training

        # Path
        self.model_path = os.path.join(self.root_dir, 'CodeBERT_model')
        self.dataset_name = 2195
        # 使用绝对路径
        self.folder_path = os.path.join(self.root_dir, 'data', str(self.dataset_name), 'cpp')
        self.excel_path = os.path.join(self.root_dir, 'data', str(self.dataset_name), '打分表.xlsx')
        self.npy_path = os.path.join(self.root_dir, 'data', str(self.dataset_name), 'code_sequences.npy')
        self.model_name = 'CodeBERTCNN_' + str(self.dataset_name)
        self.result_path = os.path.join(self.root_dir, 'result', self.model_name, 'log.txt')

        # CNN Parameter
        self.num_classes = 5  # 类别数
        self.code_length = 512  # 句子最大长度
        self.embedding_size = 768  # 词向量维度
        self.num_channels = [32, 32, 32, 32]
        self.kernel_size = [2, 3, 4, 5]  # 卷积核长度
        self.dropout = 0.3  # dropout概率

        # Train Parameter
        self.learning_rate = 0.01  # 学习率大小
        self.train_batch_size = 8
        self.test_batch_size = 8
        self.epoch = 50
        
        # 大模型评估配置
        self.use_llm = True  # 是否使用大模型评估
        self.llm_weight = 0.7  # 大模型评分权重
        self.traditional_weight = 0.3  # 传统模型评分权重
        self.llm_timeout = 10  # API调用超时时间(秒)

    # 应用程序密钥 - 从环境变量读取
    # 生产环境必须设置 SECRET_KEY 环境变量
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        # 开发环境生成临时密钥，生产环境会报错
        import sys
        if 'pytest' not in sys.modules:  # 非测试环境
            print("⚠️  警告: SECRET_KEY 未设置，使用临时生成的密钥（仅限开发环境）")
            print("   生产环境请在 .env 文件中设置 SECRET_KEY")
        SECRET_KEY = secrets.token_hex(32)
    
    # 会话配置
    SESSION_COOKIE_AGE = None
    
    # 数据库配置
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AI API配置 - 从环境变量读取
    ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    
    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max-limit
    
    # 分页配置
    ITEMS_PER_PAGE = 10

    @staticmethod
    def init_app(app):
        """初始化应用配置"""
        pass


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    
    # 开发环境数据库配置
    # 从环境变量读取，如果没有则使用本地开发默认值
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///dev_student_code_review.db'  # 默认使用SQLite作为开发数据库
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            app.logger.info("ℹ️  开发环境: 使用 SQLite 数据库")
            app.logger.info(f"   Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
            app.logger.info(f"   Instance Path: {app.instance_path}")
            app.logger.info("   如需使用MySQL，请在 .env 中设置 DEV_DATABASE_URL")


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    
    # 测试环境使用独立的SQLite数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///test_student_code_review.db'
    
    # 测试环境禁用CSRF保护
    WTF_CSRF_ENABLED = False
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    
    # 生产环境必须从环境变量获取数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # 生产环境安全配置
    # 注意：这些设置在 app.py 的 create_app 中可能会被环境变量进一步覆盖
    SESSION_COOKIE_HTTPONLY = True  # 防止JavaScript访问Cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # 防止CSRF攻击
    PERMANENT_SESSION_LIFETIME = 86400  # Session有效期1天 (24小时)
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # 生产环境必须设置的配置项检查
        required_vars = ['DATABASE_URL', 'SECRET_KEY']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            raise RuntimeError(
                f"❌ 生产环境缺少必需的环境变量: {', '.join(missing_vars)}\n"
                f"   请在 .env 文件或服务器环境中设置这些变量"
            )
        
        # 检查SECRET_KEY强度（至少32个字符）
        if len(os.environ.get('SECRET_KEY', '')) < 32:
            raise RuntimeError(
                "❌ SECRET_KEY 长度不足，生产环境至少需要32个字符\n"
                "   建议使用: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        
        # 检查是否配置了AI API密钥
        if not os.environ.get('ZHIPU_API_KEY') and not os.environ.get('OPENAI_API_KEY'):
            print("⚠️  警告: 未配置 AI API 密钥，AI评估功能将不可用")
            print("   请在 .env 中设置 ZHIPU_API_KEY 或 OPENAI_API_KEY")
        
        print("✅ 生产环境配置检查通过")

# 配置字典，用于在app.py中选择配置
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    
    'default': DevelopmentConfig
}
