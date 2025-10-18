"""
Gunicorn配置文件 - 生产环境部署
"""
import multiprocessing
import os

# 服务器socket
# 绑定到本地回环地址，不对外暴露，通过Nginx反向代理访问
bind = "127.0.0.1:5000"
backlog = 2048

# 工作进程
# 推荐的worker数量为 CPU核心数 * 2 + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"  # 同步worker，适合CPU密集型任务
worker_connections = 1000
max_requests = 1000  # 每个worker处理多少请求后重启，防止内存泄漏
max_requests_jitter = 50  # 添加随机抖动，避免所有worker同时重启

# 超时设置
# AI调用可能需要较长时间，设置为120秒
timeout = 120
keepalive = 5
graceful_timeout = 30

# 日志配置
# 确保logs目录存在
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

accesslog = os.path.join(log_dir, 'gunicorn_access.log')
errorlog = os.path.join(log_dir, 'gunicorn_error.log')
loglevel = os.environ.get('LOG_LEVEL', 'info')  # debug, info, warning, error, critical

# 访问日志格式
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "codesense"

# 守护进程设置
# 使用PM2或supervisor管理时设为False
daemon = False

# 性能优化
# 预加载应用可以节省内存，但重启时间会变长
preload_app = True

# 服务器钩子
def on_starting(server):
    """服务器启动时的回调"""
    print("=" * 60)
    print("Gunicorn服务器正在启动...")
    print(f"绑定地址: {bind}")
    print(f"工作进程数: {workers}")
    print(f"超时时间: {timeout}秒")
    print(f"日志目录: {log_dir}")
    print("=" * 60)

def on_reload(server):
    """配置重载时的回调"""
    print("Gunicorn配置已重新加载")

def when_ready(server):
    """服务器准备就绪时的回调"""
    print("✅ Gunicorn服务器已准备就绪，开始接受请求")

def worker_int(worker):
    """worker进程被中断时的回调"""
    print(f"⚠️  Worker {worker.pid} 接收到中断信号")

def worker_abort(worker):
    """worker进程超时被终止时的回调"""
    print(f"❌ Worker {worker.pid} 超时被终止")

def post_worker_init(worker):
    """worker进程初始化完成后的回调"""
    print(f"✅ Worker {worker.pid} 初始化完成")

# 安全设置
# 限制请求行、请求头字段数量和大小，防止恶意请求
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# SSL配置（如果直接使用Gunicorn处理HTTPS，不推荐）
# 推荐使用Nginx处理SSL
# keyfile = 'path/to/keyfile'
# certfile = 'path/to/certfile'

