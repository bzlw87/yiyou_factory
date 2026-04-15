"""
配置文件 - 存放项目所有的配置参数
测试改用使用
敏感信息（密钥、数据库密码）从 .env 文件读取，不写在代码里。
.env 文件位于项目根目录，已在 .gitignore 中排除。
"""
import os
from dotenv import load_dotenv

# 获取当前文件所在的目录路径，用来定位项目根目录
basedir = os.path.abspath(os.path.dirname(__file__))

# 加载 .env 文件中的环境变量
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """
    基础配置类 - 所有环境共用的配置写在这里

    SECRET_KEY 和 DATABASE_URL 必须在 .env 文件中配置。
    如果 .env 缺失或变量未设置，启动时会直接报错，避免用不安全的默认值运行。
    """
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError('SECRET_KEY 未设置，请在 .env 文件中配置')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError('DATABASE_URL 未设置，请在 .env 文件中配置')

    # 关闭 SQLAlchemy 的修改追踪功能（节省内存，我们用不到）
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 每页显示多少条记录（分页用）
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    """开发环境配置 - 你在自己电脑上开发时用这个"""
    DEBUG = True  # 开启调试模式，代码修改后自动重启，报错会显示详细信息


class ProductionConfig(Config):
    """生产环境配置 - 部署到云服务器时用这个"""
    DEBUG = False  # 关闭调试模式，不暴露错误细节给用户


# 配置字典，方便通过字符串切换配置
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
