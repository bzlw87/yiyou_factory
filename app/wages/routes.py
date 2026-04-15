"""
工资模块 - 统一的员工工资管理，对齐纸质账本
"""
from decimal import Decimal
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.wages import wages_bp
from app.models import Employee, WageRecord
from app.helpers import permission_required, log_operation, record_to_dict
from app import db
from sqlalchemy import func
import logging


@wages_bp.route('/')
@login_required
@permission_required('wages', 'view')
def employee_list():
    """员工列表"""
    position = request.args.get('position', '', type=str).strip()
    query = Employee.query
    if position:
        query = query.filter(Employee.position == position)
    employees = query.order_by(Employee.is_active.desc(), Employee.name).all()

    # 获取所有岗位用于筛选
    positions = db.session.query(Employee.position).distinct().order_by(Employee.position).all()
    positions = [p[0] for p in positions]

    # 每人本年已发月数
    current_year = date.today().year
    for emp in employees:
        emp.paid_months = WageRecord.query.filter(
            WageRecord.employee_id == emp.id,
            WageRecord.year == current_year,
            WageRecord.month >= 1,
            WageRecord.is_paid == True
        ).count()
        emp.total_months = WageRecord.query.filter(
            WageRecord.employee_id == emp.id,
            WageRecord.year == current_year,
            WageRecord.month >= 1, WageRecord.month <= 12
        ).count()

    return render_template('wages/employee_list.html',
                           employees=employees, positions=positions,
                           position=position, current_year=current_year)


@wages_bp.route('/employee/create', methods=['GET', 'POST'])
@login_required
@permission_required('wages', 'edit')
def employee_create():
    if request.method == 'POST':
        try:
            emp = Employee(
                name=request.form['name'].strip(),
                position=request.form['position'].strip(),
                base_salary=Decimal(request.form['base_salary']) if request.form.get('base_salary') else None,
                rent_subsidy=Decimal(request.form['rent_subsidy']) if request.form.get('rent_subsidy') else 0,
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(emp)
            db.session.commit()
            flash('员工添加成功！', 'success')
            return redirect(url_for('wages.employee_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('wages/employee_form.html', employee=None)


@wages_bp.route('/employee/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('wages', 'edit')
def employee_edit(id):
    emp = Employee.query.get_or_404(id)
    if request.method == 'POST':
        try:
            emp.name = request.form['name'].strip()
            emp.position = request.form['position'].strip()
            emp.base_salary = Decimal(request.form['base_salary']) if request.form.get('base_salary') else None
            emp.rent_subsidy = Decimal(request.form['rent_subsidy']) if request.form.get('rent_subsidy') else 0
            emp.is_active = 'is_active' in request.form
            emp.remark = request.form.get('remark', '').strip()
            db.session.commit()
            flash('员工信息更新成功！', 'success')
            return redirect(url_for('wages.employee_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('wages/employee_form.html', employee=emp)


@wages_bp.route('/detail/<int:emp_id>')
@login_required
@permission_required('wages', 'view')
def wage_detail(emp_id):
    """某员工的全年工资记录"""
    emp = Employee.query.get_or_404(emp_id)
    year = request.args.get('year', date.today().year, type=int)

    records = WageRecord.query.filter_by(employee_id=emp_id, year=year)\
        .order_by(WageRecord.month).all()

    # 汇总
    total_gross = sum(float(r.gross_wage or 0) for r in records if r.month >= 1)
    total_deduction = sum(float(r.deduction or 0) for r in records if r.month >= 1)
    total_net = sum(float(r.net_wage or 0) for r in records)
    paid_count = sum(1 for r in records if r.is_paid and r.month >= 1 and r.month <= 12)

    # 可选年份列表
    years = db.session.query(WageRecord.year).filter_by(employee_id=emp_id)\
        .distinct().order_by(WageRecord.year.desc()).all()
    years = [y[0] for y in years]
    if year not in years:
        years.append(year)
        years.sort(reverse=True)

    return render_template('wages/wage_detail.html',
                           emp=emp, records=records, year=year, years=years,
                           total_gross=total_gross, total_deduction=total_deduction,
                           total_net=total_net, paid_count=paid_count)


@wages_bp.route('/record/create/<int:emp_id>', methods=['GET', 'POST'])
@login_required
@permission_required('wages', 'edit')
def record_create(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    if request.method == 'POST':
        try:
            r = WageRecord(
                employee_id=emp_id,
                year=int(request.form['year']),
                month=int(request.form['month']),
                gross_wage=Decimal(request.form['gross_wage']) if request.form.get('gross_wage') else None,
                rest_days=int(request.form['rest_days']) if request.form.get('rest_days') else None,
                deduction=Decimal(request.form['deduction']) if request.form.get('deduction') else 0,
                net_wage=Decimal(request.form['net_wage']) if request.form.get('net_wage') else None,
                is_paid='is_paid' in request.form,
                paid_date=request.form['paid_date'] if request.form.get('paid_date') else None,
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(r)
            db.session.flush()
            log_operation('wages', r.id, '新增', after=record_to_dict(r))
            db.session.commit()
            flash('工资记录添加成功！', 'success')
            return redirect(url_for('wages.wage_detail', emp_id=emp_id, year=r.year))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')

    year = request.args.get('year', date.today().year, type=int)
    return render_template('wages/record_form.html', emp=emp, record=None, year=year)


@wages_bp.route('/record/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('wages', 'edit')
def record_edit(id):
    r = WageRecord.query.get_or_404(id)
    emp = r.employee
    if request.method == 'POST':
        try:
            before = record_to_dict(r)
            r.year = int(request.form['year'])
            r.month = int(request.form['month'])
            r.gross_wage = Decimal(request.form['gross_wage']) if request.form.get('gross_wage') else None
            r.rest_days = int(request.form['rest_days']) if request.form.get('rest_days') else None
            r.deduction = Decimal(request.form['deduction']) if request.form.get('deduction') else 0
            r.net_wage = Decimal(request.form['net_wage']) if request.form.get('net_wage') else None
            r.is_paid = 'is_paid' in request.form
            r.paid_date = request.form['paid_date'] if request.form.get('paid_date') else None
            r.remark = request.form.get('remark', '').strip()
            log_operation('wages', r.id, '编辑', before=before, after=record_to_dict(r))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('wages.wage_detail', emp_id=emp.id, year=r.year))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')
    return render_template('wages/record_form.html', emp=emp, record=r, year=r.year)


@wages_bp.route('/record/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('wages', 'edit')
def record_delete(id):
    r = WageRecord.query.get_or_404(id)
    emp_id = r.employee_id
    year = r.year
    try:
        before = record_to_dict(r)
        db.session.delete(r)
        log_operation('wages', id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('wages.wage_detail', emp_id=emp_id, year=year))
