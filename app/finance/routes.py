"""
财务模块 - 应收账款、应付账款、原材料采购、收付款、应收应付调整
"""
from io import BytesIO
from decimal import Decimal
from datetime import datetime, date
import openpyxl
from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from app.finance import finance_bp
from app.models import (Customer, Supplier, DeliveryOrder, PaymentReceived,
                        RawMaterialPurchase, PaymentMade, RawMaterialType,
                        ReceivableAdjustment, PayableAdjustment)
from app.helpers import permission_required, log_operation, record_to_dict
from app import db
from sqlalchemy import func
import logging


# ========== 应收账款 ==========

@finance_bp.route('/receivables')
@login_required
@permission_required('finance', 'view')
def receivables():
    customers = Customer.query.order_by(Customer.name).all()
    data = []
    for c in customers:
        total_delivery = db.session.query(func.sum(DeliveryOrder.total_cost))\
            .filter(DeliveryOrder.customer_id == c.id).scalar() or 0
        total_adjust = db.session.query(func.sum(ReceivableAdjustment.amount))\
            .filter(ReceivableAdjustment.customer_id == c.id).scalar() or 0
        total_received = db.session.query(func.sum(PaymentReceived.amount))\
            .filter(PaymentReceived.customer_id == c.id).scalar() or 0
        total_receivable = float(total_delivery) + float(total_adjust)
        balance = total_receivable - float(total_received)
        if total_receivable > 0 or float(total_received) > 0:
            data.append({
                'customer': c,
                'total_delivery': float(total_delivery),
                'total_adjust': float(total_adjust),
                'total_receivable': total_receivable,
                'total_received': float(total_received),
                'balance': balance
            })
    return render_template('finance/receivables.html', data=data)


@finance_bp.route('/receivables/export')
@login_required
@permission_required('finance', 'view')
def receivables_export():
    customers = Customer.query.order_by(Customer.name).all()
    rows = []
    for c in customers:
        total_delivery = db.session.query(func.sum(DeliveryOrder.total_cost))\
            .filter(DeliveryOrder.customer_id == c.id).scalar() or 0
        total_adjust = db.session.query(func.sum(ReceivableAdjustment.amount))\
            .filter(ReceivableAdjustment.customer_id == c.id).scalar() or 0
        total_received = db.session.query(func.sum(PaymentReceived.amount))\
            .filter(PaymentReceived.customer_id == c.id).scalar() or 0
        total_receivable = float(total_delivery) + float(total_adjust)
        balance = total_receivable - float(total_received)
        if total_receivable > 0 or float(total_received) > 0:
            rows.append((c.name, float(total_delivery), total_receivable, float(total_received), balance))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '应收账款'
    ws.append(['客户', '送货合计', '应收总额', '已收金额', '欠款余额'])
    for row in rows:
        ws.append(list(row))

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     download_name=f'应收账款_{date.today().strftime("%Y%m%d")}.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@finance_bp.route('/receivables/<int:customer_id>')
@login_required
@permission_required('finance', 'view')
def receivable_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    deliveries = DeliveryOrder.query.filter_by(customer_id=customer_id)\
        .order_by(DeliveryOrder.delivery_date.desc()).all()
    adjustments = ReceivableAdjustment.query.filter_by(customer_id=customer_id)\
        .order_by(ReceivableAdjustment.adjust_date.desc()).all()
    payments = PaymentReceived.query.filter_by(customer_id=customer_id)\
        .order_by(PaymentReceived.payment_date.desc()).all()
    total_delivery = sum(float(d.total_cost or 0) for d in deliveries)
    total_adjust = sum(float(a.amount) for a in adjustments)
    total_receivable = total_delivery + total_adjust
    total_received = sum(float(p.amount) for p in payments)
    balance = total_receivable - total_received
    return render_template('finance/receivable_detail.html',
                           customer=customer, deliveries=deliveries,
                           adjustments=adjustments, payments=payments,
                           total_delivery=total_delivery,
                           total_adjust=total_adjust,
                           total_receivable=total_receivable,
                           total_received=total_received, balance=balance)


@finance_bp.route('/payment-received/create/<int:customer_id>', methods=['GET', 'POST'])
@login_required
@permission_required('finance', 'edit')
def payment_received_create(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        try:
            p = PaymentReceived(
                customer_id=customer_id,
                payment_date=datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date(),
                amount=Decimal(request.form['amount']),
                method=request.form.get('method', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(p)
            db.session.flush()
            log_operation('payment_in', p.id, '新增', after=record_to_dict(p))
            db.session.commit()
            flash('收款记录添加成功！', 'success')
            return redirect(url_for('finance.receivable_detail', customer_id=customer_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('finance/payment_received_form.html', customer=customer, payment=None)


@finance_bp.route('/payment-received/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('finance', 'edit')
def payment_received_delete(id):
    p = PaymentReceived.query.get_or_404(id)
    customer_id = p.customer_id
    try:
        before = record_to_dict(p)
        db.session.delete(p)
        log_operation('payment_in', id, '删除', before=before)
        db.session.commit()
        flash('收款记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('finance.receivable_detail', customer_id=customer_id))


# ========== 应收调整 ==========

@finance_bp.route('/receivable-adjust/create/<int:customer_id>', methods=['GET', 'POST'])
@login_required
@permission_required('finance', 'edit')
def receivable_adjust_create(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        try:
            a = ReceivableAdjustment(
                customer_id=customer_id,
                adjust_date=datetime.strptime(request.form['adjust_date'], '%Y-%m-%d').date(),
                amount=Decimal(request.form['amount']),
                reason=request.form['reason'].strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(a)
            db.session.flush()
            log_operation('receivable_adjust', a.id, '新增', after=record_to_dict(a))
            db.session.commit()
            flash('应收调整添加成功！', 'success')
            return redirect(url_for('finance.receivable_detail', customer_id=customer_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('finance/receivable_adjust_form.html', customer=customer)


@finance_bp.route('/receivable-adjust/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('finance', 'edit')
def receivable_adjust_delete(id):
    a = ReceivableAdjustment.query.get_or_404(id)
    customer_id = a.customer_id
    try:
        before = record_to_dict(a)
        db.session.delete(a)
        log_operation('receivable_adjust', id, '删除', before=before)
        db.session.commit()
        flash('应收调整已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('finance.receivable_detail', customer_id=customer_id))


# ========== 应付账款 ==========

@finance_bp.route('/payables')
@login_required
@permission_required('finance', 'view')
def payables():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    data = []
    for s in suppliers:
        total_purchase = db.session.query(func.sum(RawMaterialPurchase.total_amount))\
            .filter(RawMaterialPurchase.supplier_id == s.id).scalar() or 0
        total_adjust = db.session.query(func.sum(PayableAdjustment.amount))\
            .filter(PayableAdjustment.supplier_id == s.id).scalar() or 0
        total_paid = db.session.query(func.sum(PaymentMade.amount))\
            .filter(PaymentMade.supplier_id == s.id).scalar() or 0
        total_payable = float(total_purchase) + float(total_adjust)
        balance = total_payable - float(total_paid)
        if total_payable > 0 or float(total_paid) > 0:
            data.append({
                'supplier': s,
                'total_purchase': float(total_purchase),
                'total_adjust': float(total_adjust),
                'total_payable': total_payable,
                'total_paid': float(total_paid),
                'balance': balance
            })
    return render_template('finance/payables.html', data=data)


@finance_bp.route('/payables/export')
@login_required
@permission_required('finance', 'view')
def payables_export():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    rows = []
    for s in suppliers:
        total_purchase = db.session.query(func.sum(RawMaterialPurchase.total_amount))\
            .filter(RawMaterialPurchase.supplier_id == s.id).scalar() or 0
        total_adjust = db.session.query(func.sum(PayableAdjustment.amount))\
            .filter(PayableAdjustment.supplier_id == s.id).scalar() or 0
        total_paid = db.session.query(func.sum(PaymentMade.amount))\
            .filter(PaymentMade.supplier_id == s.id).scalar() or 0
        total_payable = float(total_purchase) + float(total_adjust)
        balance = total_payable - float(total_paid)
        if total_payable > 0 or float(total_paid) > 0:
            rows.append((s.name, float(total_purchase), total_payable, float(total_paid), balance))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '应付账款'
    ws.append(['供应商', '采购合计', '应付总额', '已付金额', '欠款余额'])
    for row in rows:
        ws.append(list(row))

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     download_name=f'应付账款_{date.today().strftime("%Y%m%d")}.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@finance_bp.route('/payables/<int:supplier_id>')
@login_required
@permission_required('finance', 'view')
def payable_detail(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    purchases = RawMaterialPurchase.query.filter_by(supplier_id=supplier_id)\
        .order_by(RawMaterialPurchase.purchase_date.desc()).all()
    adjustments = PayableAdjustment.query.filter_by(supplier_id=supplier_id)\
        .order_by(PayableAdjustment.adjust_date.desc()).all()
    payments = PaymentMade.query.filter_by(supplier_id=supplier_id)\
        .order_by(PaymentMade.payment_date.desc()).all()
    total_purchase = sum(float(p.total_amount or 0) for p in purchases)
    total_adjust = sum(float(a.amount) for a in adjustments)
    total_payable = total_purchase + total_adjust
    total_paid = sum(float(p.amount) for p in payments)
    balance = total_payable - total_paid
    return render_template('finance/payable_detail.html',
                           supplier=supplier, purchases=purchases,
                           adjustments=adjustments, payments=payments,
                           total_purchase=total_purchase,
                           total_adjust=total_adjust,
                           total_payable=total_payable,
                           total_paid=total_paid, balance=balance)


# ========== 原材料采购 ==========

@finance_bp.route('/purchases')
@login_required
@permission_required('finance', 'view')
def purchase_list():
    page = request.args.get('page', 1, type=int)
    supplier_id = request.args.get('supplier_id', '', type=str).strip()

    query = RawMaterialPurchase.query
    if supplier_id:
        query = query.filter(RawMaterialPurchase.supplier_id == int(supplier_id))

    pagination = query.order_by(RawMaterialPurchase.purchase_date.desc()).paginate(
        page=page, per_page=20, error_out=False)

    suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template('finance/purchases.html',
                           records=pagination.items, pagination=pagination,
                           suppliers=suppliers, supplier_id=supplier_id)


@finance_bp.route('/purchases/create', methods=['GET', 'POST'])
@login_required
@permission_required('finance', 'edit')
def purchase_create():
    if request.method == 'POST':
        try:
            record = RawMaterialPurchase(
                purchase_date=datetime.strptime(request.form['purchase_date'], '%Y-%m-%d').date(),
                supplier_id=int(request.form['supplier_id']),
                material_type_id=int(request.form['material_type_id']),
                weight_tons=Decimal(request.form['weight_tons']),
                unit_price=Decimal(request.form['unit_price']),
                remark=request.form.get('remark', '').strip()
            )
            record.calculate_total()
            db.session.add(record)
            db.session.flush()
            log_operation('raw_material', record.id, '新增', after=record_to_dict(record))
            db.session.commit()
            flash('采购记录添加成功！', 'success')
            return redirect(url_for('finance.purchase_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')

    suppliers = Supplier.query.order_by(Supplier.name).all()
    material_types = RawMaterialType.query.filter_by(is_active=True).order_by(RawMaterialType.name).all()
    return render_template('finance/purchase_form.html', record=None,
                           suppliers=suppliers, material_types=material_types)


@finance_bp.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('finance', 'edit')
def purchase_edit(id):
    record = RawMaterialPurchase.query.get_or_404(id)
    if request.method == 'POST':
        try:
            before = record_to_dict(record)
            record.purchase_date = datetime.strptime(request.form['purchase_date'], '%Y-%m-%d').date()
            record.supplier_id = int(request.form['supplier_id'])
            record.material_type_id = int(request.form['material_type_id'])
            record.weight_tons = Decimal(request.form['weight_tons'])
            record.unit_price = Decimal(request.form['unit_price'])
            record.remark = request.form.get('remark', '').strip()
            record.calculate_total()
            log_operation('raw_material', record.id, '编辑', before=before, after=record_to_dict(record))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('finance.purchase_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')

    suppliers = Supplier.query.order_by(Supplier.name).all()
    material_types = RawMaterialType.query.filter_by(is_active=True).order_by(RawMaterialType.name).all()
    return render_template('finance/purchase_form.html', record=record,
                           suppliers=suppliers, material_types=material_types)


@finance_bp.route('/purchases/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('finance', 'edit')
def purchase_delete(id):
    record = RawMaterialPurchase.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        db.session.delete(record)
        log_operation('raw_material', id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('finance.purchase_list'))


@finance_bp.route('/payment-made/create/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
@permission_required('finance', 'edit')
def payment_made_create(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'POST':
        try:
            p = PaymentMade(
                supplier_id=supplier_id,
                payment_date=datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date(),
                amount=Decimal(request.form['amount']),
                method=request.form.get('method', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(p)
            db.session.flush()
            log_operation('payment_out', p.id, '新增', after=record_to_dict(p))
            db.session.commit()
            flash('付款记录添加成功！', 'success')
            return redirect(url_for('finance.payable_detail', supplier_id=supplier_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('finance/payment_made_form.html', supplier=supplier, payment=None)


@finance_bp.route('/payment-made/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('finance', 'edit')
def payment_made_delete(id):
    p = PaymentMade.query.get_or_404(id)
    supplier_id = p.supplier_id
    try:
        before = record_to_dict(p)
        db.session.delete(p)
        log_operation('payment_out', id, '删除', before=before)
        db.session.commit()
        flash('付款记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('finance.payable_detail', supplier_id=supplier_id))


# ========== 应付调整 ==========

@finance_bp.route('/payable-adjust/create/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
@permission_required('finance', 'edit')
def payable_adjust_create(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'POST':
        try:
            a = PayableAdjustment(
                supplier_id=supplier_id,
                adjust_date=datetime.strptime(request.form['adjust_date'], '%Y-%m-%d').date(),
                amount=Decimal(request.form['amount']),
                reason=request.form['reason'].strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(a)
            db.session.flush()
            log_operation('payable_adjust', a.id, '新增', after=record_to_dict(a))
            db.session.commit()
            flash('应付调整添加成功！', 'success')
            return redirect(url_for('finance.payable_detail', supplier_id=supplier_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')
    return render_template('finance/payable_adjust_form.html', supplier=supplier)


@finance_bp.route('/payable-adjust/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('finance', 'edit')
def payable_adjust_delete(id):
    a = PayableAdjustment.query.get_or_404(id)
    supplier_id = a.supplier_id
    try:
        before = record_to_dict(a)
        db.session.delete(a)
        log_operation('payable_adjust', id, '删除', before=before)
        db.session.commit()
        flash('应付调整已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('finance.payable_detail', supplier_id=supplier_id))


# ========== 账目总结 ==========

@finance_bp.route('/summary')
@login_required
@permission_required('finance', 'view')
def summary():
    """自选时间段账目总结"""
    from datetime import date
    from app.models import WageRecord

    # 默认本月1号到今天
    today = date.today()
    default_start = date(today.year, today.month, 1).isoformat()
    default_end = today.isoformat()

    date_from_str = request.args.get('date_from', default_start, type=str).strip()
    date_to_str = request.args.get('date_to', default_end, type=str).strip()

    try:
        start = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        end = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except ValueError:
        start = date(today.year, today.month, 1)
        end = today

    # 送货金额
    delivery_total = db.session.query(func.sum(DeliveryOrder.total_cost)).filter(
        DeliveryOrder.delivery_date >= start,
        DeliveryOrder.delivery_date <= end
    ).scalar() or 0

    delivery_count = DeliveryOrder.query.filter(
        DeliveryOrder.delivery_date >= start,
        DeliveryOrder.delivery_date <= end
    ).count()

    # 收款
    received_total = db.session.query(func.sum(PaymentReceived.amount)).filter(
        PaymentReceived.payment_date >= start,
        PaymentReceived.payment_date <= end
    ).scalar() or 0

    # 原材料采购
    purchase_total = db.session.query(func.sum(RawMaterialPurchase.total_amount)).filter(
        RawMaterialPurchase.purchase_date >= start,
        RawMaterialPurchase.purchase_date <= end
    ).scalar() or 0

    # 付款
    paid_total = db.session.query(func.sum(PaymentMade.amount)).filter(
        PaymentMade.payment_date >= start,
        PaymentMade.payment_date <= end
    ).scalar() or 0

    # 工资（按发放日期筛选）
    wage_total = db.session.query(func.sum(WageRecord.net_wage)).filter(
        WageRecord.paid_date >= start,
        WageRecord.paid_date <= end,
        WageRecord.is_paid == True
    ).scalar() or 0

    # 按客户统计送货
    customer_deliveries = db.session.query(
        Customer.name,
        func.sum(DeliveryOrder.total_cost),
        func.count(DeliveryOrder.id)
    ).join(Customer).filter(
        DeliveryOrder.delivery_date >= start,
        DeliveryOrder.delivery_date <= end
    ).group_by(Customer.name).order_by(func.sum(DeliveryOrder.total_cost).desc()).all()

    # 按供应商统计采购
    supplier_purchases = db.session.query(
        Supplier.name,
        func.sum(RawMaterialPurchase.total_amount),
        func.count(RawMaterialPurchase.id)
    ).join(Supplier).filter(
        RawMaterialPurchase.purchase_date >= start,
        RawMaterialPurchase.purchase_date <= end
    ).group_by(Supplier.name).order_by(func.sum(RawMaterialPurchase.total_amount).desc()).all()

    return render_template('finance/summary.html',
                           start=start, end=end,
                           delivery_total=float(delivery_total),
                           delivery_count=delivery_count,
                           received_total=float(received_total),
                           purchase_total=float(purchase_total),
                           paid_total=float(paid_total),
                           wage_total=float(wage_total),
                           customer_deliveries=customer_deliveries,
                           supplier_purchases=supplier_purchases)
