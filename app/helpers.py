"""
工具函数 - 权限检查、操作日志等公共功能
"""
import json
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

# 字段中文标签映射
_FIELD_LABELS = {
    'receive_date': '收货日期', 'delivery_date': '送货日期',
    'customer_name': '客户名称', 'customer_id': '客户',
    'yarn_count': '织数', 'yarn_type': '品种', 'variety_id': '品种',
    'quantity': '件数', 'unit_weight': '单件重量', 'total_weight': '总重量',
    'remark': '备注', 'vat_number': '缸次', 'vat_batch': '缸次',
    'total_ends': '总经根数', 'planned_length': '设定板长', 'color': '颜色',
    'order_number': '单号', 'board_length': '板长', 'dyeing_length': '染色长度',
    'yarn_used': '用纱', 'yarn_remaining': '余纱', 'rate': '费率',
    'total_cost': '费用合计', 'sizing_length': '浆长',
    'production_id': '关联工艺', 'supplier_id': '供应商',
    'material_type_id': '原材料品种', 'weight_tons': '重量(t)',
    'unit_price': '单价', 'total_amount': '应付金额',
    'payment_date': '付款日期', 'amount': '金额', 'method': '方式',
    'wage_date': '日期', 'employee_name': '员工', 'wage_month': '月份',
    'base_salary': '基本工资', 'attendance_days': '出勤天数',
    'overtime': '加班费', 'deduction': '扣款', 'net_salary': '实发工资',
    'purchase_date': '采购日期',
}
_SKIP_FIELDS = {'id', 'created_at', 'updated_at'}


def record_to_dict(record):
    result = {}
    for col in record.__table__.columns:
        val = getattr(record, col.name)
        if val is None:
            result[col.name] = None
        elif hasattr(val, 'isoformat'):
            result[col.name] = val.isoformat()
        else:
            result[col.name] = str(val)
    return result


def log_operation(module, record_id, action, before=None, after=None):
    from app.models import OperationLog
    from app import db
    log = OperationLog(
        user_id=current_user.id,
        module=module,
        record_id=record_id,
        action=action,
        before_data=json.dumps(before, ensure_ascii=False) if before is not None else None,
        after_data=json.dumps(after, ensure_ascii=False) if after is not None else None,
    )
    db.session.add(log)


def compute_diff(before_json, after_json):
    if not before_json or not after_json:
        return []
    try:
        before = json.loads(before_json)
        after = json.loads(after_json)
        diffs = []
        for key in sorted(set(before) | set(after)):
            if key in _SKIP_FIELDS:
                continue
            if str(before.get(key)) != str(after.get(key)):
                diffs.append({
                    'field': _FIELD_LABELS.get(key, key),
                    'old': before.get(key),
                    'new': after.get(key),
                })
        return diffs
    except Exception:
        return []


def get_record_logs(module, record_id):
    from app.models import OperationLog
    logs = OperationLog.query.filter_by(module=module, record_id=record_id)\
        .order_by(OperationLog.operated_at.desc()).all()
    for log in logs:
        log.diffs = compute_diff(log.before_data, log.after_data)
    return logs


def permission_required(module, action='view'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not current_user.has_permission(module, action):
                flash('您没有权限执行此操作', 'danger')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('此功能仅管理员可用', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def resolve_variety(name):
    """
    根据品种名称查找或自动创建品种记录，返回 variety_id。
    名称为空返回 None。
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    from app.models import YarnVariety
    from app import db
    v = YarnVariety.query.filter_by(name=name).first()
    if not v:
        v = YarnVariety(name=name, is_active=True)
        db.session.add(v)
        db.session.flush()
    return v.id


def resolve_customer(name):
    """
    根据客户名称查找或自动创建客户记录，返回 customer_id。
    名称为空返回 None。
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    from app.models import Customer
    from app import db
    c = Customer.query.filter_by(name=name).first()
    if not c:
        c = Customer(name=name)
        db.session.add(c)
        db.session.flush()
    return c.id
