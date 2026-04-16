# 益友染织生产管理系统 V2

常州市益友染织有限公司（牛仔布浆染厂）内部生产管理系统。

## 技术栈

- **后端**：Flask + SQLAlchemy + Flask-Login + Flask-Migrate + Flask-WTF（CSRF 全站防护）
- **数据库**：MySQL 8.0（utf8mb4）
- **前端**：Bootstrap 5 + Jinja2 模板
- **部署**：腾讯云轻量服务器（Ubuntu 22.04）+ Gunicorn + Nginx
- **配置**：python-dotenv（`.env` 文件管理环境变量）
- **服务器 IP**：101.43.91.152

## 项目规模

- Python 后端：~2800 行（21个文件）
- HTML 模板：~2100 行（47个模板）
- 数据库表：20 张
- 模块：8 个功能模块 + 系统管理

## 业务流程

```
客户送纱 → 原料入库 → 安排工艺（缸次号）→ 生产加工 → 用纱核算 → 送货结算 → 收款
                                                                         ↑
工厂买耗材 → 原材料采购 → 付款给供应商                                    财务管理
工资发放 → 员工工资管理（新增即已发）
```

## 数据库表（20张）

### 基础管理
- `customers` — 客户
- `suppliers` — 供应商
- `yarn_varieties` — 纱线品种
- `raw_material_types` — 原材料品种（靛蓝、浆料等）

### 用户权限
- `users` — 用户账号
- `permissions` — 模块权限（6个模块 × 查看/编辑）

### 生产核心
- `production_orders` — 客户工艺（核心表，缸次号唯一标识，含 `is_completed` 进行中/已完成状态）
- `material_receives` — 原料入库（通过 production_id 关联缸次，可后补）
- `yarn_consumptions` — 用纱核算（一条记录 = 纸质账本一行）

### 送货
- `delivery_orders` — 送货记录主表
- `delivery_details` — 送货单缸号明细

### 财务
- `payments_received` — 收款记录
- `receivable_adjustments` — 应收调整（期初余额等）
- `raw_material_purchases` — 原材料采购
- `payments_made` — 付款记录
- `payable_adjustments` — 应付调整

### 工资
- `employees` — 员工（姓名、岗位、基本月薪、在职状态）
- `wage_records` — 工资记录（每人每月一行，新增即代表已发放，`created_at` 为发放时间）
- `wage_rates` — 工资费率（预留）

### 系统
- `operation_logs` — 操作日志

## 功能模块

### 1. 首页（仪表盘）
- 本月数据概览（从本月1号到今天）
- 最近原料入库 / 客户工艺 / 送货记录

### 2. 原料入库
- 客户送纱登记
- 客户字段：datalist（可选 + 可输入新客户，自动创建）
- 关联缸次：先选客户再选缸次，只显示该客户最近2个月的未完成缸次
- 关联缸次可后补（来纱时可能还不知道用在哪个缸次）
- 标签带单位：单件重量(kg)、总重量(t)

### 3. 客户工艺
- 每批生产的基本信息（缸次号、客户、织数、品种、总经根数、颜色等）
- 缸次号全局唯一，是整个系统的核心标识
- 品种字段：datalist（可选 + 可输入新品种，自动创建）
- 支持"进行中 / 已完成"状态切换，默认只显示进行中

### 4. 用纱核算
- 一条记录对应纸质账本一行
- 字段：来纱来源 + 来纱（织数+品种+重量）+ 本次用量 + 余下（织数+品种+重量）
- 来纱来源：文本字段，可写"客户送纱"或"来自缸次XXX余纱"
- 先选客户再选缸次，只显示该客户最近2个月的未完成缸次
- 品种字段：datalist

### 5. 全流程追溯
- 输入缸次号，一个页面看完：客户工艺 → 原料入库 → 用纱核算 → 送货记录

### 6. 送货记录
- 送货单（单号、日期、客户、缸次、板长、颜色、来纱品种、费率等）
- 费率自动带入：同客户+同品种+同颜色匹配历史费率，只在费率为空时填入
- 缸号明细：一张送货单可包含多个缸号
- 费用合计 = 板长 × 费率（自动计算）
- 送货费用自动汇入应收账款

### 7. 财务管理
- **应收账款**：按客户汇总（送货合计 + 手动调整 - 已收 = 欠款余额）
- **应付账款**：按供应商汇总（采购合计 + 手动调整 - 已付 = 欠款余额）
- **原材料采购**：靛蓝、浆料等耗材采购记录
- **收款/付款**：登记收付款
- **账目总结**：自选日期范围（开始日期-结束日期），显示送货金额、收款、采购、付款、工资、收支差额，按客户/供应商分别统计

### 8. 工资管理
- 统一模块（不再分整经/浆染）
- 员工列表：姓名、岗位、基本月薪、在职状态、今年已发月数
- 工资详情：每人一页，按年查看全年工资记录
- **新增即代表已发放**，`created_at` 为发放时间，无需额外勾选"已发"
- 每月一行：应发工资、休息天数、扣款、实发金额、备注
- 年终奖/补贴用 `month=0` 表示
- 底部自动汇总全年数据

### 9. 系统管理
- 用户管理 + 权限管理（6个模块独立控制查看/编辑）
- 客户管理 / 供应商管理 / 品种管理 / 原材料品种管理
- 操作日志（所有增删改都有记录）

## 权限体系

6个模块独立控制：
| 模块 | 权限key |
|------|---------|
| 原料入库 | materials |
| 客户工艺 | production |
| 用纱核算 | consumption |
| 送货记录 | delivery |
| 财务管理 | finance |
| 工资管理 | wages |

## 环境变量配置

复制 `.env.example` 为 `.env` 并填写实际值：
```bash
cp .env.example .env
# 编辑 .env，填写数据库连接、SECRET_KEY 等
```

`.env` 文件不提交到 Git，服务器上单独维护。

## 开发与部署流程

### 日常开发流程（本地 → 服务器）
```bash
# 本地修改完成后
git add .
git commit -m "说明改了什么"
git push                        # 推送到 Gitee

# SSH 登录服务器
cd /home/yiyou/yiyou_factory
git pull                        # 拉取最新代码
sudo systemctl restart yiyou    # 重启服务
```

### 有数据库字段变更时（migrate）
```bash
su - yiyou
cd yiyou_factory
source venv/bin/activate
flask db migrate -m "描述变更内容"
flask db upgrade
exit
sudo systemctl restart yiyou
```

### 首次建库部署（删库重建，会清空数据）
```bash
mysql -u yiyou -pLEIwu123 -e "DROP DATABASE yiyou_factory; CREATE DATABASE yiyou_factory CHARACTER SET utf8mb4;"
su - yiyou
cd yiyou_factory
source venv/bin/activate
python init_db.py
exit
sudo systemctl restart yiyou
```

注意：yiyou 用户没有 sudo 权限，需要 su root 执行管理命令。

## 数据库备份

服务器定时备份脚本：`/home/yiyou/backup_db.sh`，定期自动备份 MySQL 数据。
如需手动执行备份：
```bash
bash /home/yiyou/backup_db.sh
```

## 已知待修复问题

### 安全修复（已完成）
- [x] CSRF 防护（Flask-WTF 全站启用）
- [x] float → Decimal 统一处理金额/费率
- [x] 管理员自锁防护（不能删除/禁用自己）

### 长期维护（重要但不急）
- [ ] 数据导出功能（Excel）
- [ ] 客户欠款一览页面
- [ ] 追溯查询改精确匹配走 DeliveryDetail（当前 contains 会误命中）

### 已确认不改的（有意设计）
- 客户/品种自动创建：用户明确要求的便利性
- 重量字段存文本："11T+500kg"是纸质账本格式，拆数值+单位反而丢信息
- 费率三条件匹配：已和用户确认过，三条件够用
