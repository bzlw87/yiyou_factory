# 益友染织生产管理系统 - 完整部署指南

> 本指南假设你是 Python 零基础初学者，每一步都写得非常详细。
> 请严格按照顺序执行，不要跳过任何步骤。

---

## 目录

1. [项目结构说明](#1-项目结构说明)
2. [本地开发环境搭建](#2-本地开发环境搭建)
3. [云服务器部署（阿里云/腾讯云）](#3-云服务器部署)
4. [域名配置和 HTTPS](#4-域名配置和-https)
5. [日常维护命令](#5-日常维护命令)
6. [常见报错和解决方法](#6-常见报错和解决方法)

---

## 1. 项目结构说明

```
yiyou_factory/                 ← 项目根目录
├── config.py                  ← 配置文件（数据库地址、密钥等）
├── run.py                     ← 开发环境启动入口
├── wsgi.py                    ← 生产环境启动入口（Gunicorn 用）
├── init_db.py                 ← 数据库初始化脚本（首次必须执行）
├── requirements.txt           ← Python 依赖包列表
├── .env.example               ← 环境变量模板
├── deploy/                    ← 部署配置文件
│   ├── nginx_yiyou.conf       ← Nginx 配置
│   └── yiyou.service          ← Systemd 服务配置（开机自启）
└── app/                       ← 应用主目录
    ├── __init__.py             ← 应用工厂（创建 Flask 应用）
    ├── models.py               ← 数据库模型（所有表的定义）
    ├── helpers.py              ← 工具函数（权限检查等）
    ├── auth/routes.py          ← 登录认证
    ├── dashboard/routes.py     ← 首页仪表盘
    ├── materials/routes.py     ← 模块一：原料入库
    ├── production/routes.py    ← 模块二：生产排单
    ├── consumption/routes.py   ← 模块三：用纱核算
    ├── warping/routes.py       ← 模块四：整经记录
    ├── delivery/routes.py      ← 模块五：送货记录
    ├── admin/routes.py         ← 管理员模块
    ├── templates/              ← HTML 模板文件
    └── static/css/style.css    ← 自定义样式
```

---

## 2. 本地开发环境搭建

### 2.1 安装 Python

**Windows：**
1. 访问 https://www.python.org/downloads/ 下载 Python 3.11+
2. **安装时一定勾选 "Add Python to PATH"**
3. 安装后打开命令提示符（Win+R → 输入 cmd → 回车），验证：
```bash
python --version
```

**Mac：**
```bash
brew install python
```

### 2.2 安装 MySQL

**Windows：** 下载 MySQL Installer：https://dev.mysql.com/downloads/installer/
**Mac：** `brew install mysql && brew services start mysql`

### 2.3 创建数据库

打开 MySQL 命令行，执行：
```sql
CREATE DATABASE yiyou_factory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'yiyou'@'localhost' IDENTIFIED BY 'YiYou2026!';
GRANT ALL PRIVILEGES ON yiyou_factory.* TO 'yiyou'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```
> 把 `YiYou2026!` 改成你自己的密码

### 2.4 配置项目

编辑 `config.py`，修改数据库密码：
```python
'mysql+pymysql://yiyou:YiYou2026!@localhost:3306/yiyou_factory?charset=utf8mb4'
```

### 2.5 安装 Python 依赖

```bash
cd yiyou_factory
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 安装依赖（国内用清华镜像加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.6 初始化数据库
```bash
python init_db.py
```

### 2.7 启动项目
```bash
python run.py
```
浏览器访问 http://127.0.0.1:5000，用 admin / admin123 登录。

---

## 3. 云服务器部署

### 3.1 购买云服务器
- 阿里云 ECS / 腾讯云 CVM
- 系统选 **Ubuntu 22.04 LTS**
- 最低 2核4GB
- 安全组开放端口：22、80、443

### 3.2 SSH 连接服务器
```bash
ssh root@你的服务器IP
```

### 3.3 服务器初始化
```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git nginx mysql-server
systemctl start mysql && systemctl enable mysql
mysql_secure_installation
```

### 3.4 创建数据库
```bash
mysql -u root -p
```
```sql
CREATE DATABASE yiyou_factory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'yiyou'@'localhost' IDENTIFIED BY '设一个强密码';
GRANT ALL PRIVILEGES ON yiyou_factory.* TO 'yiyou'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3.5 创建系统用户并上传代码
```bash
adduser yiyou
# 从你的电脑上传（在本地终端执行）:
scp -r yiyou_factory/ root@服务器IP:/home/yiyou/
# 然后在服务器上:
chown -R yiyou:yiyou /home/yiyou/yiyou_factory
```

### 3.6 安装依赖
```bash
su - yiyou
cd /home/yiyou/yiyou_factory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3.7 修改配置并初始化
```bash
nano config.py   # 改数据库密码
python3 init_db.py
python3 run.py    # 测试运行，Ctrl+C 停止
exit              # 回到 root
```

### 3.8 配置 Gunicorn 服务
```bash
cp /home/yiyou/yiyou_factory/deploy/yiyou.service /etc/systemd/system/
nano /etc/systemd/system/yiyou.service
# 修改 SECRET_KEY 和 DATABASE_URL
# SECRET_KEY 用这个命令生成: python3 -c "import secrets; print(secrets.token_hex(32))"

systemctl daemon-reload
systemctl start yiyou
systemctl enable yiyou
systemctl status yiyou   # 确认显示 active (running)
```

### 3.9 配置 Nginx
```bash
cp /home/yiyou/yiyou_factory/deploy/nginx_yiyou.conf /etc/nginx/sites-available/yiyou_factory
nano /etc/nginx/sites-available/yiyou_factory
# 改 server_name 为你的域名或 IP

ln -s /etc/nginx/sites-available/yiyou_factory /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx && systemctl enable nginx
```

浏览器访问 http://你的服务器IP 即可使用！

---

## 4. 域名配置和 HTTPS

```bash
# 域名解析：在域名控制台添加 A 记录指向服务器 IP
# 修改 Nginx server_name 为你的域名
# 安装 HTTPS 证书：
apt install -y certbot python3-certbot-nginx
certbot --nginx -d 你的域名.com -d www.你的域名.com
```

> 中国大陆服务器需要 ICP 备案才能使用域名

---

## 5. 日常维护

```bash
systemctl restart yiyou                    # 更新代码后重启
journalctl -u yiyou -f                     # 查看实时日志
mysqldump -u yiyou -p yiyou_factory > backup.sql   # 备份数据库
mysql -u yiyou -p yiyou_factory < backup.sql       # 恢复数据库
```

---

## 6. 常见报错

| 报错信息 | 原因 | 解决方法 |
|---------|------|---------|
| `ModuleNotFoundError: No module named 'flask'` | 虚拟环境没激活 | `source venv/bin/activate` |
| `Access denied for user` | 数据库密码错误 | 检查 config.py 中的密码 |
| `Can't connect to MySQL server` | MySQL 没运行 | `sudo systemctl start mysql` |
| 502 Bad Gateway | Gunicorn 没运行 | `sudo systemctl restart yiyou` |
| CSS 样式加载不出 | Nginx 路径错误 | 检查 nginx 配置中 static 路径 |
| 手机无法访问 | 安全组没开 80 端口 | 云控制台添加安全组规则 |

---

## 默认账号

| 用户名 | 密码 | 角色 |
|-------|------|------|
| admin | admin123 | 管理员（首次登录后请立即修改！）|
