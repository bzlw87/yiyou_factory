"""
送货记录路由 - 含费率自动带入和缸号明细
"""
import json
from decimal import Decimal
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.delivery import delivery_bp
from app.models import DeliveryOrder, DeliveryDetail, Customer
from app.helpers import permission_required, log_operation, record_to_dict, get_record_logs, resolve_customer
from app import db
import logging


@delivery_bp.route('/')
@login_required
@permission_required('delivery', 'view')
def index():
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('keyword', '', type=str).strip()
    order_no = request.args.get('order_no', '', type=str).strip()
    date_from = request.args.get('date_from', '', type=str).strip()
    date_to = request.args.get('date_to', '', type=str).strip()

    query = DeliveryOrder.query.join(Customer)
    if keyword:
        query = query.filter(Customer.name.contains(keyword))
    if order_no:
        query = query.filter(DeliveryOrder.order_number.contains(order_no))
    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(DeliveryOrder.delivery_date >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(DeliveryOrder.delivery_date <= d)
        except ValueError:
            pass

    pagination = query.order_by(DeliveryOrder.delivery_date.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('delivery/index.html',
                           records=pagination.items,
                           pagination=pagination,
                           keyword=keyword, order_no=order_no,
                           date_from=date_from, date_to=date_to)


@delivery_bp.route('/api/match-rate')
@login_required
def match_rate():
    """费率自动带入API：同客户+同来纱品种+同颜色"""
    customer_name = request.args.get('customer_name', '').strip()
    yarn_type = request.args.get('yarn_type', '').strip()
    color = request.args.get('color', '').strip()
    if not customer_name:
        return jsonify({'rate': None})
    c = Customer.query.filter_by(name=customer_name).first()
    if not c:
        return jsonify({'rate': None})
    match = DeliveryOrder.query.filter(
        DeliveryOrder.customer_id == c.id,
        DeliveryOrder.yarn_type == yarn_type,
        DeliveryOrder.color == color,
        DeliveryOrder.rate.isnot(None)
    ).order_by(DeliveryOrder.created_at.desc()).first()
    if match:
        return jsonify({'rate': str(match.rate)})
    return jsonify({'rate': None})


@delivery_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('delivery', 'edit')
def create():
    if request.method == 'POST':
        try:
            record = DeliveryOrder(
                order_number=request.form['order_number'].strip(),
                delivery_date=datetime.strptime(request.form['delivery_date'], '%Y-%m-%d').date(),
                customer_id=resolve_customer(request.form.get('customer_name', '')),
                vat_batch=request.form.get('vat_batch', '').strip(),
                yarn_count=request.form.get('yarn_count', '').strip(),
                board_length=Decimal(request.form['board_length']) if request.form.get('board_length') else None,
                dyeing_length=Decimal(request.form['dyeing_length']) if request.form.get('dyeing_length') else None,
                color=request.form.get('color', '').strip(),
                yarn_type=request.form.get('yarn_type', '').strip(),
                incoming_yarn=request.form.get('incoming_yarn', '').strip(),
                yarn_used=request.form.get('yarn_used', '').strip(),
                yarn_remaining=request.form.get('yarn_remaining', '').strip(),
                rate=Decimal(request.form['rate']) if request.form.get('rate') else None,
                remark=request.form.get('remark', '').strip()
            )
            record.calculate_total_cost()
            db.session.add(record)
            db.session.flush()

            details_json = request.form.get('details_json', '[]')
            try:
                details_data = json.loads(details_json)
                if not isinstance(details_data, list):
                    raise ValueError
            except (ValueError, TypeError):
                db.session.rollback()
                flash('明细数据格式错误', 'danger')
                return redirect(url_for('delivery.create'))
            for item in details_data:
                if not item.get('vat_number'):
                    continue
                detail = DeliveryDetail(
                    delivery_id=record.id,
                    vat_number=item['vat_number'],
                    length=Decimal(item['length']) if item.get('length') else None,
                    remark=item.get('remark', '')
                )
                db.session.add(detail)

            log_operation('delivery', record.id, '新增', after=record_to_dict(record))
            db.session.commit()
            flash('送货记录添加成功！', 'success')
            return redirect(url_for('delivery.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    return render_template('delivery/form.html', record=None, details=[],
                           customers=customers)


@delivery_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('delivery', 'edit')
def edit(id):
    record = DeliveryOrder.query.get_or_404(id)
    if request.method == 'POST':
        try:
            before = record_to_dict(record)
            record.order_number = request.form['order_number'].strip()
            record.delivery_date = datetime.strptime(request.form['delivery_date'], '%Y-%m-%d').date()
            record.customer_id = resolve_customer(request.form.get('customer_name', ''))
            record.vat_batch = request.form.get('vat_batch', '').strip()
            record.yarn_count = request.form.get('yarn_count', '').strip()
            record.board_length = Decimal(request.form['board_length']) if request.form.get('board_length') else None
            record.dyeing_length = Decimal(request.form['dyeing_length']) if request.form.get('dyeing_length') else None
            record.color = request.form.get('color', '').strip()
            record.yarn_type = request.form.get('yarn_type', '').strip()
            record.incoming_yarn = request.form.get('incoming_yarn', '').strip()
            record.yarn_used = request.form.get('yarn_used', '').strip()
            record.yarn_remaining = request.form.get('yarn_remaining', '').strip()
            record.rate = Decimal(request.form['rate']) if request.form.get('rate') else None
            record.remark = request.form.get('remark', '').strip()
            record.calculate_total_cost()

            DeliveryDetail.query.filter_by(delivery_id=record.id).delete()
            details_json = request.form.get('details_json', '[]')
            try:
                details_data = json.loads(details_json)
                if not isinstance(details_data, list):
                    raise ValueError
            except (ValueError, TypeError):
                db.session.rollback()
                flash('明细数据格式错误', 'danger')
                return redirect(url_for('delivery.edit', id=record.id))
            for item in details_data:
                if not item.get('vat_number'):
                    continue
                detail = DeliveryDetail(
                    delivery_id=record.id,
                    vat_number=item['vat_number'],
                    length=Decimal(item['length']) if item.get('length') else None,
                    remark=item.get('remark', '')
                )
                db.session.add(detail)

            log_operation('delivery', record.id, '编辑', before=before, after=record_to_dict(record))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('delivery.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    details = record.details.all()
    details_list = [{'vat_number': d.vat_number or '', 'length': float(d.length) if d.length else '',
                     'remark': d.remark or ''} for d in details]
    return render_template('delivery/form.html', record=record, details=details_list,
                           customers=customers)


@delivery_bp.route('/view/<int:id>')
@login_required
@permission_required('delivery', 'view')
def view_record(id):
    record = DeliveryOrder.query.get_or_404(id)
    details = record.details.all()
    logs = get_record_logs('delivery', id)
    return render_template('delivery/view.html', record=record, details=details, logs=logs)


@delivery_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('delivery', 'edit')
def delete(id):
    record = DeliveryOrder.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        record_id = record.id
        db.session.delete(record)
        log_operation('delivery', record_id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('delivery.index'))
