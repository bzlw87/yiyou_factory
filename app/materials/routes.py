"""
原料入库路由
"""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.materials import materials_bp
from app.models import MaterialReceive, Customer, YarnVariety, ProductionOrder
from app.helpers import permission_required, log_operation, record_to_dict, resolve_variety, resolve_customer
from app import db
import logging


@materials_bp.route('/')
@login_required
@permission_required('materials', 'view')
def index():
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('keyword', '', type=str).strip()
    date_from = request.args.get('date_from', '', type=str).strip()
    date_to = request.args.get('date_to', '', type=str).strip()

    query = MaterialReceive.query.join(Customer)
    if keyword:
        query = query.filter(Customer.name.contains(keyword))
    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(MaterialReceive.receive_date >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(MaterialReceive.receive_date <= d)
        except ValueError:
            pass

    pagination = query.order_by(MaterialReceive.receive_date.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('materials/index.html',
                           records=pagination.items,
                           pagination=pagination,
                           keyword=keyword,
                           date_from=date_from, date_to=date_to)


@materials_bp.route('/api/productions')
@login_required
@permission_required('materials', 'view')
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
        ProductionOrder.created_at >= two_months_ago,
        ProductionOrder.is_completed == False
    ).order_by(ProductionOrder.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'vat_number': r.vat_number,
    } for r in records])


@materials_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('materials', 'edit')
def create():
    if request.method == 'POST':
        try:
            prod_id = int(request.form['production_id']) if request.form.get('production_id') else None
            customer_id = resolve_customer(request.form.get('customer_name', ''))
            # 如果选了关联缸次，校验客户一致
            if prod_id and customer_id:
                prod = ProductionOrder.query.get(prod_id)
                if prod and prod.customer_id != customer_id:
                    flash('关联缸次与选择的客户不一致', 'danger')
                    return redirect(url_for('materials.create'))

            record = MaterialReceive(
                receive_date=datetime.strptime(request.form['receive_date'], '%Y-%m-%d').date(),
                customer_id=customer_id,
                yarn_count=request.form['yarn_count'].strip(),
                variety_id=resolve_variety(request.form.get('variety_name', '')),
                quantity=int(request.form['quantity']),
                unit_weight=request.form.get('unit_weight', '').strip(),
                total_weight=request.form.get('total_weight', '').strip(),
                production_id=prod_id,
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(record)
            db.session.flush()
            log_operation('materials', record.id, '新增', after=record_to_dict(record))
            db.session.commit()
            flash('收货记录添加成功！', 'success')
            return redirect(url_for('materials.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    varieties = YarnVariety.query.filter_by(is_active=True).order_by(YarnVariety.name).all()
    return render_template('materials/form.html', record=None,
                           customers=customers, varieties=varieties)


@materials_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('materials', 'edit')
def edit(id):
    record = MaterialReceive.query.get_or_404(id)
    if request.method == 'POST':
        try:
            before = record_to_dict(record)
            prod_id = int(request.form['production_id']) if request.form.get('production_id') else None
            customer_id = resolve_customer(request.form.get('customer_name', ''))
            if prod_id and customer_id:
                prod = ProductionOrder.query.get(prod_id)
                if prod and prod.customer_id != customer_id:
                    flash('关联缸次与选择的客户不一致', 'danger')
                    return redirect(url_for('materials.edit', id=id))

            record.receive_date = datetime.strptime(request.form['receive_date'], '%Y-%m-%d').date()
            record.customer_id = customer_id
            record.yarn_count = request.form['yarn_count'].strip()
            record.variety_id = resolve_variety(request.form.get('variety_name', ''))
            record.quantity = int(request.form['quantity'])
            record.unit_weight = request.form.get('unit_weight', '').strip()
            record.total_weight = request.form.get('total_weight', '').strip()
            record.production_id = prod_id
            record.remark = request.form.get('remark', '').strip()
            log_operation('materials', record.id, '编辑', before=before, after=record_to_dict(record))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('materials.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    varieties = YarnVariety.query.filter_by(is_active=True).order_by(YarnVariety.name).all()
    return render_template('materials/form.html', record=record,
                           customers=customers, varieties=varieties)


@materials_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('materials', 'edit')
def delete(id):
    record = MaterialReceive.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        record_id = record.id
        db.session.delete(record)
        log_operation('materials', record_id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，请检查后重试', 'danger')
    return redirect(url_for('materials.index'))
