"""
Flask 应用工厂 - 益友染织生产管理系统 V2
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录后再访问此页面'
login_manager.login_message_category = 'warning'


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 注册蓝图
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/')

    from app.materials import materials_bp
    app.register_blueprint(materials_bp, url_prefix='/materials')

    from app.production import production_bp
    app.register_blueprint(production_bp, url_prefix='/production')

    from app.consumption import consumption_bp
    app.register_blueprint(consumption_bp, url_prefix='/consumption')

    from app.delivery import delivery_bp
    app.register_blueprint(delivery_bp, url_prefix='/delivery')

    from app.finance import finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')

    from app.wages import wages_bp
    app.register_blueprint(wages_bp, url_prefix='/wages')

    from app.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # 模板全局函数
    from flask import request, url_for as _url_for

    @app.template_global()
    def url_for_page(endpoint, page):
        params = dict(request.args)
        params['page'] = page
        return _url_for(endpoint, **params)

    # 错误处理
    from flask import render_template, redirect, request, flash, url_for

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash('页面已过期，请重新操作', 'warning')
        return redirect(request.referrer or url_for('dashboard.index'))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('500.html'), 500

    return app
