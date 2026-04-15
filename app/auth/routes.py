"""
认证路由 - 处理登录和登出请求

路由（Route）就是 URL 地址和处理函数的对应关系。
比如用户访问 /auth/login 这个地址时，就会执行 login() 函数。
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app.auth import auth_bp
from app.models import User
from app import db
import logging


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    登录页面

    GET 请求：显示登录表单
    POST 请求：验证用户名和密码
    """
    # 如果用户已经登录了，直接跳转到首页
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # 根据用户名查找用户
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('用户名或密码错误', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active_user:
            flash('此账号已被禁用，请联系管理员', 'warning')
            return redirect(url_for('auth.login'))

        # 登录成功，记住用户状态
        login_user(user, remember=request.form.get('remember', False))
        flash(f'欢迎回来，{user.display_name}！', 'success')

        # 如果用户之前想访问某个页面但被要求登录，登录后跳转回那个页面
        next_page = request.args.get('next')
        if next_page:
            parsed = urlparse(next_page)
            # 只允许站内跳转（没有域名的相对路径）
            if parsed.netloc == '' and parsed.scheme == '':
                return redirect(next_page)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required  # 这个装饰器表示必须登录才能访问
def logout():
    """登出"""
    logout_user()
    flash('您已成功退出登录', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """修改密码"""
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(old_password):
            flash('原密码错误', 'danger')
            return redirect(url_for('auth.change_password'))

        if new_password != confirm_password:
            flash('两次输入的新密码不一致', 'danger')
            return redirect(url_for('auth.change_password'))

        if len(new_password) < 6:
            flash('新密码长度不能少于6位', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_password)
        db.session.commit()
        flash('密码修改成功', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/change_password.html')
