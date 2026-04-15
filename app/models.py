"""
数据库模型定义 - 益友染织生产管理系统 V2

所有数据表的结构定义。
每个 class 对应数据库里的一张表，每个 Column 对应一个字段。

表分类：
  基础管理：customers, suppliers, yarn_varieties, raw_material_types
  用户权限：users, permissions
  生产核心：production_orders（核心）, material_receives, yarn_consumptions
  送货：delivery_orders, delivery_details
  财务：payments_received, raw_material_purchases, payments_made
  工资：employees, wage_records, wage_rates
  系统：operation_logs
"""

from decimal import Decimal
from datetime import datetime, date, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

# 北京时间 UTC+8
_CST = timezone(timedelta(hours=8))


def _now_cst():
    return datetime.now(_CST).replace(tzinfo=None)


# ============================================================
# 基础管理表
# ============================================================

class Customer(db.Model):
    """客户管理 - 所有模块共用的客户下拉选择"""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    contact = db.Column(db.String(50))       # 联系人
    phone = db.Column(db.String(50))         # 电话
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)

    # 关联关系
    production_orders = db.relationship('ProductionOrder', backref='customer', lazy='dynamic')
    material_receives = db.relationship('MaterialReceive', backref='customer', lazy='dynamic')
    delivery_orders = db.relationship('DeliveryOrder', backref='customer', lazy='dynamic')
    payments_received = db.relationship('PaymentReceived', backref='customer', lazy='dynamic')
    receivable_adjustments = db.relationship('ReceivableAdjustment', backref='customer', lazy='dynamic')


class Supplier(db.Model):
    """供应商管理 - 原材料采购用"""
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    contact = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)

    # 关联关系
    purchases = db.relationship('RawMaterialPurchase', backref='supplier', lazy='dynamic')
    payments_made = db.relationship('PaymentMade', backref='supplier', lazy='dynamic')
    payable_adjustments = db.relationship('PayableAdjustment', backref='supplier', lazy='dynamic')


class YarnVariety(db.Model):
    """品种管理 - 纱线品种下拉选择（客户的纱，如棉涤丝）"""
    __tablename__ = 'yarn_varieties'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now_cst)


class RawMaterialType(db.Model):
    """原材料品种管理 - 工厂自己的耗材（靛蓝、浆料等）"""
    __tablename__ = 'raw_material_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    unit = db.Column(db.String(20))          # 默认单位
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now_cst)


# ============================================================
# 用户与权限
# ============================================================

class User(UserMixin, db.Model):
    """用户表"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now_cst)

    permissions = db.relationship('Permission', backref='user', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, module, action='view'):
        if self.role == 'admin':
            return True
        perm = self.permissions.filter_by(module=module).first()
        if perm is None:
            return False
        if action == 'view':
            return perm.can_view
        elif action == 'edit':
            return perm.can_edit
        return False

    @property
    def is_admin(self):
        return self.role == 'admin'


class Permission(db.Model):
    """权限表 - 按模块控制查看/编辑权限"""
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    can_view = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'module', name='uq_user_module'),)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================
# 生产核心表
# ============================================================

class ProductionOrder(db.Model):
    """
    客户工艺 - 整个系统的核心表

    缸次号（vat_number）是全局唯一标识，其他模块通过 production_id 关联到这里。
    """
    __tablename__ = 'production_orders'

    id = db.Column(db.Integer, primary_key=True)
    vat_number = db.Column(db.String(50), nullable=False, unique=True, index=True)  # 缸次号，唯一
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    yarn_count = db.Column(db.String(50))        # 织数
    variety_id = db.Column(db.Integer, db.ForeignKey('yarn_varieties.id'))
    total_ends = db.Column(db.Integer)            # 总经根数
    planned_length = db.Column(db.Numeric(12, 2)) # 设定板长(m)
    color = db.Column(db.String(50))              # 加工颜色
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)
    updated_at = db.Column(db.DateTime, default=_now_cst, onupdate=_now_cst)

    # 关联关系
    variety = db.relationship('YarnVariety', backref='production_orders')
    material_receives = db.relationship('MaterialReceive', backref='production_order', lazy='dynamic')
    yarn_consumptions = db.relationship('YarnConsumption', backref='production_order', lazy='dynamic')


class MaterialReceive(db.Model):
    """
    原料入库 - 客户送纱登记

    来纱的时候可能还不知道用在哪个缸次，所以 production_id 允许为空，后面再补。
    """
    __tablename__ = 'material_receives'

    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=True)  # 可为空，后补
    receive_date = db.Column(db.Date, nullable=False, default=date.today)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    yarn_count = db.Column(db.String(50), nullable=False)    # 织数
    variety_id = db.Column(db.Integer, db.ForeignKey('yarn_varieties.id'))
    quantity = db.Column(db.Integer, nullable=False)          # 件数/包数
    unit_weight = db.Column(db.String(50), nullable=False)    # 单件重量
    total_weight = db.Column(db.String(50))                   # 总重量
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)
    updated_at = db.Column(db.DateTime, default=_now_cst, onupdate=_now_cst)

    # 关联关系
    variety = db.relationship('YarnVariety', backref='material_receives')


class YarnConsumption(db.Model):
    """
    用纱核算 - 生产结算底稿，对应纸质记录的一行

    字段完全对齐纸质账本：
    缸次 | 板长 | 浆长 | 来纱(织数+品种+重量) | 本次用量 | 余下(织数+品种+重量) | 备注
    """
    __tablename__ = 'yarn_consumptions'

    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    board_length = db.Column(db.Numeric(12, 2))    # 板长(m)
    sizing_length = db.Column(db.Numeric(12, 2))   # 浆长(m)
    # 来纱信息（可能是客户送的，也可能是上一缸次余下的）
    incoming_source = db.Column(db.String(200))      # 来纱来源（如"客户送纱"或"来自缸次260XXX余纱"）
    incoming_yarn_count = db.Column(db.String(50))   # 来纱织数
    incoming_variety = db.Column(db.String(100))     # 来纱品种
    incoming_weight = db.Column(db.String(100))      # 来纱重量（如 "11T" 或 "11T+500kg"）
    # 本次用量
    usage_weight = db.Column(db.String(100))         # 本次浆染用的重量
    # 余下信息（将来会成为下一个缸次的来纱）
    remaining_yarn_count = db.Column(db.String(50))  # 余下织数
    remaining_variety = db.Column(db.String(100))     # 余下品种
    remaining_weight = db.Column(db.String(100))      # 余下重量
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)
    updated_at = db.Column(db.DateTime, default=_now_cst, onupdate=_now_cst)


# ============================================================
# 送货
# ============================================================

class DeliveryOrder(db.Model):
    """
    送货记录主表

    费率自动带入逻辑：同客户+同织数+同来纱品种+同总经根数+同颜色，五个条件全匹配。
    费用合计 = 染色长度 * 费率
    """
    __tablename__ = 'delivery_orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    delivery_date = db.Column(db.Date, nullable=False, default=date.today)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    vat_batch = db.Column(db.String(50))              # 缸次
    yarn_count = db.Column(db.String(50))             # 织数
    board_length = db.Column(db.Numeric(12, 2))       # 板长(m)
    dyeing_length = db.Column(db.Numeric(12, 2))      # 染色长度(m)
    color = db.Column(db.String(50))                   # 颜色
    yarn_type = db.Column(db.String(200))              # 来纱品种
    incoming_yarn = db.Column(db.String(100))          # 来纱数量
    yarn_used = db.Column(db.String(100))              # 用纱数量
    yarn_remaining = db.Column(db.String(100))         # 余纱数量
    rate = db.Column(db.Numeric(10, 4))                # 费率（元/m）
    total_cost = db.Column(db.Numeric(12, 2))          # 费用合计
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)
    updated_at = db.Column(db.DateTime, default=_now_cst, onupdate=_now_cst)

    # 关联缸号明细
    details = db.relationship('DeliveryDetail', backref='delivery_order', lazy='dynamic',
                              cascade='all, delete-orphan', order_by='DeliveryDetail.id')

    def calculate_total_cost(self):
        if self.dyeing_length and self.rate:
            self.total_cost = round(Decimal(self.dyeing_length) * Decimal(self.rate), 2)


class DeliveryDetail(db.Model):
    """送货单缸号明细"""
    __tablename__ = 'delivery_details'

    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery_orders.id'), nullable=False)
    vat_number = db.Column(db.String(50), nullable=False)
    length = db.Column(db.Numeric(12, 2))
    remark = db.Column(db.Text)


# ============================================================
# 财务：应收（收款）+ 应付（原材料采购 + 付款）
# ============================================================

class PaymentReceived(db.Model):
    """
    收款记录 - 客户付给我们的钱

    应收账款 = 该客户所有送货单 total_cost 之和 - 该客户所有收款 amount 之和
    """
    __tablename__ = 'payments_received'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    method = db.Column(db.String(50))        # 收款方式（转账、现金等）
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)


class ReceivableAdjustment(db.Model):
    """
    应收调整 - 手动添加的应收金额

    用于录入期初余额（系统上线前客户已有的欠款），
    或其他不走送货单的特殊应收。
    """
    __tablename__ = 'receivable_adjustments'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    adjust_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # 正数=增加应收，负数=减少应收
    reason = db.Column(db.String(200), nullable=False)      # 原因（如"期初余额"）
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)


class RawMaterialPurchase(db.Model):
    """
    原材料采购记录 - 我们买耗材（靛蓝、浆料等）

    应付金额 = 重量(t) * 单价(元/t)，自动计算
    """
    __tablename__ = 'raw_material_purchases'

    id = db.Column(db.Integer, primary_key=True)
    purchase_date = db.Column(db.Date, nullable=False, default=date.today)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    material_type_id = db.Column(db.Integer, db.ForeignKey('raw_material_types.id'), nullable=False)
    weight_tons = db.Column(db.Numeric(12, 4), nullable=False)    # 重量(t)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)     # 单价(元/t)
    total_amount = db.Column(db.Numeric(12, 2))                    # 应付金额，自动算
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)

    # 关联关系
    material_type = db.relationship('RawMaterialType', backref='purchases')

    def calculate_total(self):
        if self.weight_tons and self.unit_price:
            self.total_amount = round(Decimal(self.weight_tons) * Decimal(self.unit_price), 2)


class PaymentMade(db.Model):
    """
    付款记录 - 我们付给供应商的钱

    应付账款 = 该供应商所有采购 total_amount 之和 - 该供应商所有付款 amount 之和
    """
    __tablename__ = 'payments_made'

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    method = db.Column(db.String(50))
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)


class PayableAdjustment(db.Model):
    """
    应付调整 - 手动添加的应付金额

    用于录入期初余额（系统上线前欠供应商的钱），
    或其他不走采购单的特殊应付。
    """
    __tablename__ = 'payable_adjustments'

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    adjust_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)


# ============================================================
# 工资
# ============================================================

class Employee(db.Model):
    """
    员工表 - 工资管理用

    每个员工一条记录，记录基本信息和岗位。
    """
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)        # 岗位（浆染/拉经/食料等）
    base_salary = db.Column(db.Numeric(10, 2))                  # 基本月薪（固定工资填，计件留空）
    rent_subsidy = db.Column(db.Numeric(10, 2), default=0)     # 年房租补贴（拉经1000，其他0）
    is_active = db.Column(db.Boolean, default=True)             # 在职/离职
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_cst)

    # 关联工资记录
    wage_records = db.relationship('WageRecord', backref='employee', lazy='dynamic',
                                   cascade='all, delete-orphan',
                                   order_by='WageRecord.year, WageRecord.month')


class WageRecord(db.Model):
    """
    工资记录 - 每人每月一行，对应纸质账本

    字段：月份、应发工资、休息天数、扣款、实发金额、是否已发、发放日期
    """
    __tablename__ = 'wage_records'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)               # 1-12，0=年终奖/补贴
    gross_wage = db.Column(db.Numeric(10, 2))                    # 应发工资
    rest_days = db.Column(db.Integer)                             # 休息天数
    deduction = db.Column(db.Numeric(10, 2), default=0)          # 扣款
    net_wage = db.Column(db.Numeric(10, 2))                      # 实发金额
    is_paid = db.Column(db.Boolean, default=False)               # 是否已发
    paid_date = db.Column(db.Date)                                # 发放日期
    remark = db.Column(db.Text)                                   # 备注（合发说明、年终奖类型等）
    created_at = db.Column(db.DateTime, default=_now_cst)

    __table_args__ = (db.UniqueConstraint('employee_id', 'year', 'month', name='uq_emp_year_month'),)


class WageRate(db.Model):
    """工资费率表 - 保留，可能整经工资计算时参考"""
    __tablename__ = 'wage_rates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Numeric(10, 4), nullable=False)
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now_cst)


# ============================================================
# 操作日志
# ============================================================

class OperationLog(db.Model):
    """操作日志 - 记录所有模块的增删改操作"""
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    operated_at = db.Column(db.DateTime, nullable=False, default=_now_cst)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(10), nullable=False)
    before_data = db.Column(db.Text)
    after_data = db.Column(db.Text)

    user = db.relationship('User', backref='operation_logs')
