"""
客户工艺（原生产排单）路由
"""
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.production import production_bp
from app.models import ProductionOrder, Customer, YarnVariety
from app.helpers import permission_required, log_operation, record_to_dict, resolve_variety, resolve_customer
from app import db
import logging


@production_bp.route('/')
@login_required
@permission_required('production', 'view')
def index():
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('keyword', '', type=str).strip()
    vat = request.args.get('vat', '', type=str).strip()
    show_completed = request.args.get('show_completed', '', type=str).strip()

    query = ProductionOrder.query.join(Customer)
    if keyword:
        query = query.filter(Customer.name.contains(keyword))
    if vat:
        query = query.filter(ProductionOrder.vat_number.contains(vat))
    if show_completed != 'yes':
        query = query.filter(ProductionOrder.is_completed == False)

    pagination = query.order_by(ProductionOrder.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('production/index.html',
                           records=pagination.items,
                           pagination=pagination,
                           keyword=keyword, vat=vat,
                           show_completed=show_completed)


@production_bp.route('/toggle-complete/<int:id>', methods=['POST'])
@login_required
@permission_required('production', 'edit')
def toggle_complete(id):
    record = ProductionOrder.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        record.is_completed = not record.is_completed
        log_operation('production', record.id, '编辑', before=before, after=record_to_dict(record))
        db.session.commit()
        status = '已完成' if record.is_completed else '进行中'
        flash(f'缸次 {record.vat_number} 已标记为{status}', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('操作失败，请重试', 'danger')
    show_completed = request.form.get('show_completed', '')
    return redirect(url_for('production.index', show_completed=show_completed))


@production_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('production', 'edit')
def create():
    if request.method == 'POST':
        try:
            record = ProductionOrder(
                vat_number=request.form['vat_number'].strip(),
                customer_id=resolve_customer(request.form.get('customer_name', '')),
                yarn_count=request.form.get('yarn_count', '').strip(),
                variety_id=resolve_variety(request.form.get('variety_name', '')),
                total_ends=int(request.form['total_ends']) if request.form.get('total_ends') else None,
                planned_length=Decimal(request.form['planned_length']) if request.form.get('planned_length') else None,
                color=request.form.get('color', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(record)
            db.session.flush()
            log_operation('production', record.id, '新增', after=record_to_dict(record))
            db.session.commit()
            flash('客户工艺添加成功！', 'success')
            return redirect(url_for('production.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('添加失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    varieties = YarnVariety.query.filter_by(is_active=True).order_by(YarnVariety.name).all()
    return render_template('production/form.html', record=None,
                           customers=customers, varieties=varieties)


@production_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('production', 'edit')
def edit(id):
    record = ProductionOrder.query.get_or_404(id)
    if request.method == 'POST':
        try:
            before = record_to_dict(record)
            record.vat_number = request.form['vat_number'].strip()
            record.customer_id = resolve_customer(request.form.get('customer_name', ''))
            record.yarn_count = request.form.get('yarn_count', '').strip()
            record.variety_id = resolve_variety(request.form.get('variety_name', ''))
            record.total_ends = int(request.form['total_ends']) if request.form.get('total_ends') else None
            record.planned_length = Decimal(request.form['planned_length']) if request.form.get('planned_length') else None
            record.color = request.form.get('color', '').strip()
            record.remark = request.form.get('remark', '').strip()
            log_operation('production', record.id, '编辑', before=before, after=record_to_dict(record))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('production.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f'操作异常: {e}')
            flash('更新失败，请检查输入后重试', 'danger')

    customers = Customer.query.order_by(Customer.name).all()
    varieties = YarnVariety.query.filter_by(is_active=True).order_by(YarnVariety.name).all()
    return render_template('production/form.html', record=record,
                           customers=customers, varieties=varieties)


@production_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('production', 'edit')
def delete(id):
    record = ProductionOrder.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        record_id = record.id
        db.session.delete(record)
        log_operation('production', record_id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'操作异常: {e}')
        flash('删除失败，可能存在关联数据，请检查后重试', 'danger')
    return redirect(url_for('production.index'))


# ========== 全流程追溯 ==========

@production_bp.route('/trace')
@login_required
@permission_required('production', 'view')
def trace():
    """输入缸次号，查看从来纱到送货的完整记录"""
    vat = request.args.get('vat', '', type=str).strip()
    result = None
    if vat:
        from app.models import MaterialReceive, YarnConsumption, DeliveryOrder
        order = ProductionOrder.query.filter_by(vat_number=vat).first()
        if order:
            materials = MaterialReceive.query.filter_by(production_id=order.id)\
                .order_by(MaterialReceive.receive_date).all()
            consumption = YarnConsumption.query.filter_by(production_id=order.id).first()
            deliveries = DeliveryOrder.query.filter(
                DeliveryOrder.vat_batch.contains(vat)
            ).order_by(DeliveryOrder.delivery_date).all()
            result = {
                'order': order,
                'materials': materials,
                'consumption': consumption,
                'deliveries': deliveries,
            }
        else:
            flash(f'未找到缸次号 "{vat}" 的记录', 'warning')

    return render_template('production/trace.html', vat=vat, result=result)
