"""一次性数据库维护命令。

生产 WSGI worker 不再在启动时执行 ``create_all``/``ALTER TABLE``。部署新
版本时先运行：

    python database_maintenance.py

命令会使用当前生产环境的 DATABASE_URL，创建缺失表、补历史列并检查性能
索引；不会打印连接密码，也不会启动 Web 服务器或后台 AI 任务。
"""

import os


# 必须在导入 config/app 前设置，避免生产 app factory 误启动任务线程。
os.environ.setdefault('FLASK_CONFIG', 'production')
os.environ.setdefault('AUTO_INIT_DB', '0')
os.environ.setdefault('DB_ENSURE_INDEXES', '0')
os.environ.setdefault('ASYNC_TASKS_ENABLED', '0')

from app import app  # noqa: E402  (环境变量必须先设置)
from models import init_db  # noqa: E402


if __name__ == '__main__':
    app.config['DB_AUTO_INIT'] = True
    app.config['DB_ENSURE_INDEXES'] = True
    with app.app_context():
        init_db(app)
    print('数据库维护完成。')
