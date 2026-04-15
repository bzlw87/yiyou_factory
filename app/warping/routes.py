"""
模块四：整经记录 路由

这个模块比较复杂，因为有"主表+明细"两层结构。
主表是整经任务信息，明细是每一轴的具体参数。
保存时需要同时处理主表和明细数据。
"""
import json
from decimal import Decimal
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.warping import warping_bp
from app.models import WarpingRecord, WarpingDetail, WageRate
from app.helpers import permission_required, log_operation, record_to_dict, get_record_logs
from app import db


@warping_bp.route('/')
@login_required
@permission_required('warping', 'view')
def index():
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('keyword', '', type=str).strip()
    year = request.args.get('year', '', type=str).strip()

    query = WarpingRecord.query
    if keyword:
        query = query.filter(WarpingRecord.customer_name.contains(keyword))
    if year:
        try:
            y = int(year)
            query = query.filter(db.extract('year', WarpingRecord.board_date) == y)
        except ValueError:
            pass

    pagination = query.order_by(WarpingRecord.board_date.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('warping/index.html',
                           records=pagination.items,
                           pagination=pagination,
                           keyword=keyword, year=year)


@warping_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('warping', 'edit')
def create():
    if request.method == 'POST':
        try:
            record = WarpingRecord(
                board_date=datetime.strptime(request.form['board_date'], '%Y-%m-%d').date(),
                customer_name=request.form['customer_name'].strip(),
                loom_number=request.form.get('loom_number', '').strip(),
                loom_batch=request.form.get('loom_batch', '').strip(),
                yarn_type=request.form.get('yarn_type', '').strip(),
                yarn_count=request.form.get('yarn_count', '').strip(),
                total_ends=int(request.form['total_ends']) if request.form.get('total_ends') else None,
                total_beams=int(request.form['total_beams']) if request.form.get('total_beams') else None,
                board_length=Decimal(request.form['board_length']) if request.form.get('board_length') else None,
                merge_ends=request.form.get('merge_ends', '').strip(),
                side_ends=request.form.get('side_ends', '').strip(),
                remark=request.form.get('remark', '').strip()
            )
            db.session.add(record)
            db.session.flush()  # flush 让 record 获得 id，但还没真正写入数据库

            # 处理轴次明细（从前端 JavaScript 传来的 JSON 数据）
            details_json = request.form.get('details_json', '[]')
            try:
                details_data = json.loads(details_json)
                if not isinstance(details_data, list):
                    raise ValueError
            except (ValueError, TypeError):
                db.session.rollback()
                flash('明细数据格式错误，请重新提交', 'danger')
                return redirect(url_for('warping.create'))
            for item in details_data:
                if not item.get('beam_order'):
                    continue
                detail = WarpingDetail(
                    warping_id=record.id,
                    beam_order=int(item['beam_order']),
                    head_count=item.get('head_count', ''),
                    length=Decimal(item['length']) if item.get('length') else None,
                    beam_number=item.get('beam_number', ''),
                    shift=item.get('shift', ''),
                    operator=item.get('operator', ''),
                    wage_subtotal=Decimal(item['wage_subtotal']) if item.get('wage_subtotal') else 0,
                    remark=item.get('remark', '')
                )
                db.session.add(detail)

            record.calculate_total_wage()
            log_operation('warping', record.id, '新增', after=record_to_dict(record))
            db.session.commit()
            flash('整经记录添加成功！', 'success')
            return redirect(url_for('warping.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'添加失败：{str(e)}', 'danger')

    wage_rates = WageRate.query.filter_by(is_active=True).all()
    return render_template('warping/form.html', record=None, details=[], wage_rates=wage_rates)


@warping_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('warping', 'edit')
def edit(id):
    record = WarpingRecord.query.get_or_404(id)

    if request.method == 'POST':
        try:
            before = record_to_dict(record)
            record.board_date = datetime.strptime(request.form['board_date'], '%Y-%m-%d').date()
            record.customer_name = request.form['customer_name'].strip()
            record.loom_number = request.form.get('loom_number', '').strip()
            record.loom_batch = request.form.get('loom_batch', '').strip()
            record.yarn_type = request.form.get('yarn_type', '').strip()
            record.yarn_count = request.form.get('yarn_count', '').strip()
            record.total_ends = int(request.form['total_ends']) if request.form.get('total_ends') else None
            record.total_beams = int(request.form['total_beams']) if request.form.get('total_beams') else None
            record.board_length = Decimal(request.form['board_length']) if request.form.get('board_length') else None
            record.merge_ends = request.form.get('merge_ends', '').strip()
            record.side_ends = request.form.get('side_ends', '').strip()
            record.remark = request.form.get('remark', '').strip()

            # 删除旧的明细，重新添加
            WarpingDetail.query.filter_by(warping_id=record.id).delete()

            details_json = request.form.get('details_json', '[]')
            try:
                details_data = json.loads(details_json)
                if not isinstance(details_data, list):
                    raise ValueError
            except (ValueError, TypeError):
                db.session.rollback()
                flash('明细数据格式错误，请重新提交', 'danger')
                return redirect(url_for('warping.edit', id=record.id))
            for item in details_data:
                if not item.get('beam_order'):
                    continue
                detail = WarpingDetail(
                    warping_id=record.id,
                    beam_order=int(item['beam_order']),
                    head_count=item.get('head_count', ''),
                    length=Decimal(item['length']) if item.get('length') else None,
                    beam_number=item.get('beam_number', ''),
                    shift=item.get('shift', ''),
                    operator=item.get('operator', ''),
                    wage_subtotal=Decimal(item['wage_subtotal']) if item.get('wage_subtotal') else 0,
                    remark=item.get('remark', '')
                )
                db.session.add(detail)

            record.calculate_total_wage()
            log_operation('warping', record.id, '编辑', before=before, after=record_to_dict(record))
            db.session.commit()
            flash('记录更新成功！', 'success')
            return redirect(url_for('warping.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')

    details = record.details.order_by(WarpingDetail.beam_order).all()
    details_list = [{
        'beam_order': d.beam_order,
        'head_count': d.head_count or '',
        'length': float(d.length) if d.length else '',
        'beam_number': d.beam_number or '',
        'shift': d.shift or '',
        'operator': d.operator or '',
        'wage_subtotal': float(d.wage_subtotal) if d.wage_subtotal else '',
        'remark': d.remark or ''
    } for d in details]
    wage_rates = WageRate.query.filter_by(is_active=True).all()
    return render_template('warping/form.html', record=record, details=details_list, wage_rates=wage_rates)


@warping_bp.route('/view/<int:id>')
@login_required
@permission_required('warping', 'view')
def view_record(id):
    record = WarpingRecord.query.get_or_404(id)
    details = record.details.order_by(WarpingDetail.beam_order).all()
    logs = get_record_logs('warping', id)
    return render_template('warping/view.html', record=record, details=details, logs=logs)


@warping_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('warping', 'edit')
def delete(id):
    record = WarpingRecord.query.get_or_404(id)
    try:
        before = record_to_dict(record)
        record_id = record.id
        db.session.delete(record)
        log_operation('warping', record_id, '删除', before=before)
        db.session.commit()
        flash('记录已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败：{str(e)}', 'danger')
    return redirect(url_for('warping.index'))
