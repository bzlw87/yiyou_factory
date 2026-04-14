"""
配置文件 - 存放项目所有的配置参数
为什么单独放一个文件？因为开发环境和生产环境的配置不同，
比如开发时用本地数据库，上线后用云服务器数据库，
分开管理方便切换。
"""
import os

# 获取当前文件所在的目录路径，用来定位项目根目录
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """
    基础配置类 - 所有环境共用的配置写在这里
    """
    # SECRET_KEY 是 Flask 用来加密 session（会话）的密钥
    # 实际部署时必须改成一个随机的长字符串，不能用这个默认值
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'yiyou-factory-secret-key-change-me'

    # 数据库连接地址（MySQL）
    # 格式：mysql+pymysql://用户名:密码@服务器地址:端口/数据库名?charset=utf8mb4
    # utf8mb4 支持中文和特殊字符
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://yiyou:LEIwu123@localhost:3306/yiyou_factory?charset=utf8mb4'

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
