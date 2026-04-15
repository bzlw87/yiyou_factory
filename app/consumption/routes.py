"""
用纱核算路由 - 对应纸质记录的一行一条
"""
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.consumption import consumption_bp
from app.models import YarnConsumption, ProductionOrder, Customer, YarnVariety
from app.helpers import permission_required, log_operation, record_to_dict
from app import db
import logging


@consumption_bp.route('/api/productions')
@login_required
@permission_required('consumption', 'view')
def api_productions_by_customer():
    """API：根据客户名称返回该客户最近2个月的缸次"""
    from datetime import timedelta, date
    customer_name = request.args.get('customer_name', '').strip()
    if not customer_name:
        return jsonify([])
    c = Customer.query.filter_by(name=customer_name).first()
    if not c:
        return jsonify([])
    two_months_ago = date.today() - timedelta(days=60)
    records = ProductionOrder.query.filter(
        ProductionOrder.customer_id == c.id,
        ProductionOrder.created_at >= two_months_ago
    ).order_by(ProductionOrder.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'vat_number': r.vat_number,
    } for r in records])


@consumption_bp.route('/')
@login_required
@permission_required('consumption', 'view')
def index():
    page = request.args.get('page', 1, type=int)
    vat = request.args.get('vat', '', type=str).strip()
    keyword = request.args.get('keyword', '', type=str).strip()

    query = YarnConsumption.query.join(ProductionOrder)
    if vat:
        query = query.filter(ProductionOrder.vat_number.contains(vat))
    if keyword:
        query = query.join(Customer).filter(Customer.name.contains(keyword))

    pagination = query.order_by(YarnConsumption.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('consumption/index.html',
                           records=pagination.items,
                           pagination=pagination,
                           vat=vat, keyword=keyword)


@consumption_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('consumption', 'edit')
def create():
    if request.method == 'POST':
        try:
            record = YarnConsumption(
                production_id=int(request.form['production_id']),
                board_length=Decimal(request.form['board_length']) if request.form.get('board_length') else None,
                sizing_length=Decimal(request.form['sizing_length']) if request.form.get('sizing_length') else None,
                incoming_source=request.form.get('incoming_source', '').strip(),
                incoming_yarn_count=request.form.get('incoming_yarn_count', '').strip(),
                incoming_variety=request.form.get('incoming_variety', '').strip(),
                incoming_weight=request.form.get('incoming_weight', '').strip(),
                usage_weight=request.form.get('usage_weight', '').strip(),
                remaining_yarn_count=request.form.get('remaining_yarn_count', '').strip(),
                remaining_variety=request.form.get('remaining_variety', '').strip(),
                remaining_weight=request.form.get('remaining_weight', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(record)
            db.session.flush()
            log_operation('consumption', record.id, '新增', after=record_to_dict(record))
            db.session.commit()
            flash('用纱核算记录添加成功！', 'success')
            return redirect(url_for('consumption.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    varieties = YarnVariety.query.filter_by(is_active=True).order_by(YarnVariety.name).all()
    return render_template('consumption/form.html', record=None, customers=customers, varieties=varieties)


@consumption_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('consumption', 'edit')
def edit(id):
    record = YarnConsumption.query.get_or_404(id)

    if request.method == 'POST':
        try:
            before = record_to_dict(record)
            record.production_id = int(request.form['production_id'])
            record.board_length = Decimal(request.form['board_length']) if request.form.get('board_length') else None
            record.sizing_length = Decimal(request.form['sizing_length']) if request.form.get('sizing_length') else None
            record.incoming_source = request.form.get('incoming_source', '').strip()
            record.incoming_yarn_count = request.form.get('incoming_yarn_count', '').strip()
            record.incoming_variety = request.form.get('incoming_variety', '').strip()
            record.incoming_weight = request.form.get('incoming_weight', '').strip()
            record.usage_weight = request.form.get('usage_weight', '').strip()
            record.remaining_yarn_count = request.form.get('remaining_yarn_count', '').strip()
            record.remaining_variety = request.form.get('remaining_variety', '').strip()
            record.remaining_weight = request.form.get('remaining_weight', '').strip()
            record.remark = request.form.get('remark', '').strip()
            log_operation('consumption', record.id, '编辑', before=before, after=record_to_dict(record))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('consumption.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    varieties = YarnVariety.query.filter_by(is_active=True).order_by(YarnVariety.name).all()
    return render_template('consumption/form.html', record=record, customers=customers, varieties=varieties)


@consumption_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('consumption', 'edit')
def delete(id):
    record = YarnConsumption.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        record_id = record.id
        db.session.delete(record)
        log_operation('consumption', record_id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('consumption.index'))
