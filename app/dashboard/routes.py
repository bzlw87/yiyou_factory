"""
仪表盘 - 系统首页（本月数据）
"""
from datetime import date
from flask import render_template
from flask_login import login_required
from app.dashboard import dashboard_bp
from app.models import MaterialReceive, ProductionOrder, YarnConsumption, DeliveryOrder
from app import db


@dashboard_bp.route('/')
@login_required
def index():
    today = date.today()
    month_start = date(today.year, today.month, 1)

    stats = {
        'production_count': ProductionOrder.query.filter(
            ProductionOrder.created_at >= month_start).count(),
        'materials_count': MaterialReceive.query.filter(
            MaterialReceive.receive_date >= month_start).count(),
        'delivery_count': DeliveryOrder.query.filter(
            DeliveryOrder.delivery_date >= month_start).count(),
        'consumption_count': YarnConsumption.query.filter(
            YarnConsumption.created_at >= month_start).count(),
    }

    recent_materials = MaterialReceive.query.filter(
        MaterialReceive.receive_date >= month_start
    ).order_by(MaterialReceive.receive_date.desc()).limit(5).all()

    recent_production = ProductionOrder.query.filter(
        ProductionOrder.created_at >= month_start
    ).order_by(ProductionOrder.created_at.desc()).limit(5).all()

    recent_delivery = DeliveryOrder.query.filter(
        DeliveryOrder.delivery_date >= month_start
    ).order_by(DeliveryOrder.delivery_date.desc()).limit(5).all()

    return render_template('dashboard/index.html',
                           stats=stats,
                           recent_materials=recent_materials,
                           recent_production=recent_production,
                           recent_delivery=recent_delivery,
                           month_start=month_start,
                           today=today)
