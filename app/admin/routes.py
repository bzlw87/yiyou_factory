"""
管理员模块 - 用户/权限/客户/供应商/品种/原材料品种/工资费率/操作日志
"""
from decimal import Decimal
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.admin import admin_bp
from app.models import (User, Permission, WageRate, OperationLog,
                        Customer, Supplier, YarnVariety, RawMaterialType)
from app.helpers import admin_required, compute_diff
from app import db
import logging

# 权限模块定义
MODULES = {
    'materials': '原料入库',
    'production': '客户工艺',
    'consumption': '用纱核算',
    'delivery': '送货记录',
    'finance': '财务管理',
    'wages': '工资管理',
}


# ========== 用户管理 ==========

@admin_bp.route('/users')
@login_required
@admin_required
def user_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/user_list.html', users=users)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def user_create():
    if request.method == 'POST':
        username = request.form['username'].strip()
        display_name = request.form['display_name'].strip()
        password = request.form['password']
        role = request.form.get('role', 'staff')

        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return redirect(url_for('admin.user_create'))
        if len(password) < 6:
            flash('密码长度不能少于6位', 'danger')
            return redirect(url_for('admin.user_create'))

        user = User(username=username, display_name=display_name, role=role)
        user.set_password(password)
        db.session.add(user)

        if role == 'staff':
            for module_key in MODULES:
                perm = Permission(user=user, module=module_key, can_view=False, can_edit=False)
                db.session.add(perm)

        db.session.commit()
        flash(f'用户 {display_name} 创建成功！', 'success')
        return redirect(url_for('admin.user_list'))

    return render_template('admin/user_form.html', user=None, modules=MODULES)


@admin_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_edit(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        new_role = request.form.get('role', 'staff')
        new_active = 'is_active_user' in request.form

        # 管理员自锁防护：不允许降级或禁用最后一个活跃管理员
        if user.role == 'admin':
            active_admin_count = User.query.filter_by(role='admin', is_active_user=True).count()
            if new_role != 'admin' and active_admin_count <= 1:
                flash('至少保留一个管理员账号，无法降级', 'danger')
                return redirect(url_for('admin.user_edit', id=id))
            if not new_active and active_admin_count <= 1:
                flash('至少保留一个活跃管理员账号，无法禁用', 'danger')
                return redirect(url_for('admin.user_edit', id=id))

        user.display_name = request.form['display_name'].strip()
        user.role = new_role
        user.is_active_user = new_active
        new_password = request.form.get('password', '').strip()
        if new_password:
            if len(new_password) < 6:
                flash('密码长度不能少于6位', 'danger')
                return redirect(url_for('admin.user_edit', id=id))
            user.set_password(new_password)
        db.session.commit()
        flash('用户信息更新成功！', 'success')
        return redirect(url_for('admin.user_list'))
    return render_template('admin/user_form.html', user=user, modules=MODULES)


@admin_bp.route('/users/permissions/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_permissions(id):
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash('管理员拥有所有权限，无需单独设置', 'info')
        return redirect(url_for('admin.user_list'))

    if request.method == 'POST':
        for module_key in MODULES:
            perm = Permission.query.filter_by(user_id=user.id, module=module_key).first()
            if not perm:
                perm = Permission(user_id=user.id, module=module_key)
                db.session.add(perm)
            perm.can_view = f'{module_key}_view' in request.form
            perm.can_edit = f'{module_key}_edit' in request.form
        db.session.commit()
        flash('权限设置已更新！', 'success')
        return redirect(url_for('admin.user_list'))

    perms = {}
    for module_key in MODULES:
        perm = Permission.query.filter_by(user_id=user.id, module=module_key).first()
        perms[module_key] = perm
    return render_template('admin/permissions.html', user=user, modules=MODULES, perms=perms)


@admin_bp.route('/users/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def user_delete(id):
    user = User.query.get_or_404(id)
    if user.id == 1:
        flash('不能删除超级管理员', 'danger')
        return redirect(url_for('admin.user_list'))
    try:
        db.session.delete(user)
        db.session.commit()
        flash('用户已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('admin.user_list'))


# ========== 客户管理 ==========

@admin_bp.route('/customers')
@login_required
def customer_list():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('admin/customer_list.html', customers=customers)


@admin_bp.route('/customers/create', methods=['GET', 'POST'])
@login_required
def customer_create():
    if request.method == 'POST':
        try:
            c = Customer(
                name=request.form['name'].strip(),
                contact=request.form.get('contact', '').strip(),
                phone=request.form.get('phone', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(c)
            db.session.commit()
            flash('客户添加成功！', 'success')
            return redirect(url_for('admin.customer_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('admin/customer_form.html', customer=None)


@admin_bp.route('/customers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def customer_edit(id):
    c = Customer.query.get_or_404(id)
    if request.method == 'POST':
        try:
            c.name = request.form['name'].strip()
            c.contact = request.form.get('contact', '').strip()
            c.phone = request.form.get('phone', '').strip()
            c.remark = request.form.get('remark', '').strip()
            db.session.commit()
            flash('客户信息更新成功！', 'success')
            return redirect(url_for('admin.customer_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('admin/customer_form.html', customer=c)


@admin_bp.route('/customers/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def customer_delete(id):
    c = Customer.query.get_or_404(id)
    try:
        db.session.delete(c)
        db.session.commit()
        flash('客户已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，可能存在关联数据，请检查后重试', 'danger')
    return redirect(url_for('admin.customer_list'))


# ========== 供应商管理 ==========

@admin_bp.route('/suppliers')
@login_required
def supplier_list():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template('admin/supplier_list.html', suppliers=suppliers)


@admin_bp.route('/suppliers/create', methods=['GET', 'POST'])
@login_required
def supplier_create():
    if request.method == 'POST':
        try:
            s = Supplier(
                name=request.form['name'].strip(),
                contact=request.form.get('contact', '').strip(),
                phone=request.form.get('phone', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(s)
            db.session.commit()
            flash('供应商添加成功！', 'success')
            return redirect(url_for('admin.supplier_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('admin/supplier_form.html', supplier=None)


@admin_bp.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def supplier_edit(id):
    s = Supplier.query.get_or_404(id)
    if request.method == 'POST':
        try:
            s.name = request.form['name'].strip()
            s.contact = request.form.get('contact', '').strip()
            s.phone = request.form.get('phone', '').strip()
            s.remark = request.form.get('remark', '').strip()
            db.session.commit()
            flash('供应商信息更新成功！', 'success')
            return redirect(url_for('admin.supplier_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('admin/supplier_form.html', supplier=s)


@admin_bp.route('/suppliers/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def supplier_delete(id):
    s = Supplier.query.get_or_404(id)
    try:
        db.session.delete(s)
        db.session.commit()
        flash('供应商已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，可能存在关联数据，请检查后重试', 'danger')
    return redirect(url_for('admin.supplier_list'))


# ========== 品种管理 ==========

@admin_bp.route('/varieties')
@login_required
def variety_list():
    varieties = YarnVariety.query.order_by(YarnVariety.name).all()
    return render_template('admin/variety_list.html', varieties=varieties)


@admin_bp.route('/varieties/create', methods=['GET', 'POST'])
@login_required
def variety_create():
    if request.method == 'POST':
        try:
            v = YarnVariety(
                name=request.form['name'].strip(),
                is_active='is_active' in request.form
            )
            db.session.add(v)
            db.session.commit()
            flash('品种添加成功！', 'success')
            return redirect(url_for('admin.variety_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('admin/variety_form.html', variety=None)


@admin_bp.route('/varieties/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def variety_edit(id):
    v = YarnVariety.query.get_or_404(id)
    if request.method == 'POST':
        try:
            v.name = request.form['name'].strip()
            v.is_active = 'is_active' in request.form
            db.session.commit()
            flash('品种更新成功！', 'success')
            return redirect(url_for('admin.variety_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('admin/variety_form.html', variety=v)


@admin_bp.route('/varieties/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def variety_delete(id):
    v = YarnVariety.query.get_or_404(id)
    try:
        db.session.delete(v)
        db.session.commit()
        flash('品种已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，可能存在关联数据，请检查后重试', 'danger')
    return redirect(url_for('admin.variety_list'))


# ========== 原材料品种管理 ==========

@admin_bp.route('/material-types')
@login_required
def material_type_list():
    types = RawMaterialType.query.order_by(RawMaterialType.name).all()
    return render_template('admin/material_type_list.html', types=types)


@admin_bp.route('/material-types/create', methods=['GET', 'POST'])
@login_required
def material_type_create():
    if request.method == 'POST':
        try:
            t = RawMaterialType(
                name=request.form['name'].strip(),
                unit=request.form.get('unit', '').strip(),
                is_active='is_active' in request.form
            )
            db.session.add(t)
            db.session.commit()
            flash('原材料品种添加成功！', 'success')
            return redirect(url_for('admin.material_type_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('admin/material_type_form.html', mtype=None)


@admin_bp.route('/material-types/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def material_type_edit(id):
    t = RawMaterialType.query.get_or_404(id)
    if request.method == 'POST':
        try:
            t.name = request.form['name'].strip()
            t.unit = request.form.get('unit', '').strip()
            t.is_active = 'is_active' in request.form
            db.session.commit()
            flash('原材料品种更新成功！', 'success')
            return redirect(url_for('admin.material_type_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('admin/material_type_form.html', mtype=t)


@admin_bp.route('/material-types/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def material_type_delete(id):
    t = RawMaterialType.query.get_or_404(id)
    try:
        db.session.delete(t)
        db.session.commit()
        flash('原材料品种已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，可能存在关联数据，请检查后重试', 'danger')
    return redirect(url_for('admin.material_type_list'))


# ========== 工资费率管理 ==========

@admin_bp.route('/wage-rates')
@login_required
def wage_rate_list():
    rates = WageRate.query.order_by(WageRate.created_at.desc()).all()
    return render_template('admin/wage_rates.html', rates=rates)


@admin_bp.route('/wage-rates/create', methods=['GET', 'POST'])
@login_required
def wage_rate_create():
    if request.method == 'POST':
        try:
            rate = WageRate(
                name=request.form['name'].strip(),
                rate=Decimal(request.form['rate']),
                description=request.form.get('description', '').strip(),
                is_active='is_active' in request.form
            )
            db.session.add(rate)
            db.session.commit()
            flash('费率添加成功！', 'success')
            return redirect(url_for('admin.wage_rate_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('admin/wage_rate_form.html', rate=None)


@admin_bp.route('/wage-rates/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def wage_rate_edit(id):
    rate = WageRate.query.get_or_404(id)
    if request.method == 'POST':
        try:
            rate.name = request.form['name'].strip()
            rate.rate = Decimal(request.form['rate'])
            rate.description = request.form.get('description', '').strip()
            rate.is_active = 'is_active' in request.form
            db.session.commit()
            flash('费率更新成功！', 'success')
            return redirect(url_for('admin.wage_rate_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('admin/wage_rate_form.html', rate=rate)


@admin_bp.route('/wage-rates/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def wage_rate_delete(id):
    rate = WageRate.query.get_or_404(id)
    try:
        db.session.delete(rate)
        db.session.commit()
        flash('费率已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('admin.wage_rate_list'))


# ========== 操作日志 ==========

@admin_bp.route('/operation-logs')
@login_required
@admin_required
def operation_log_list():
    page = request.args.get('page', 1, type=int)
    module = request.args.get('module', '', type=str).strip()
    user_id = request.args.get('user_id', '', type=str).strip()
    action = request.args.get('action', '', type=str).strip()
    date_from = request.args.get('date_from', '', type=str).strip()
    date_to = request.args.get('date_to', '', type=str).strip()

    query = OperationLog.query
    if module:
        query = query.filter(OperationLog.module == module)
    if user_id:
        query = query.filter(OperationLog.user_id == int(user_id))
    if action:
        query = query.filter(OperationLog.action == action)
    if date_from:
        try:
            query = query.filter(OperationLog.operated_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(OperationLog.operated_at < datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            pass

    pagination = query.order_by(OperationLog.operated_at.desc()).paginate(
        page=page, per_page=50, error_out=False)

    logs = pagination.items
    for log in logs:
        log.diffs = compute_diff(log.before_data, log.after_data)

    # 合并新旧模块名
    all_modules = dict(MODULES)
    all_modules.update({'raw_material': '原材料采购', 'payment_in': '收款记录', 'payment_out': '付款记录'})

    users = User.query.order_by(User.display_name).all()
    return render_template('admin/operation_log.html',
                           logs=logs, pagination=pagination,
                           modules=all_modules, users=users,
                           module=module, user_id=user_id, action=action,
                           date_from=date_from, date_to=date_to)
