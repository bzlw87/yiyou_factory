"""
数据库初始化脚本 - 首次运行时执行
python init_db.py
"""
from app import create_app, db
from app.models import User, Permission, WageRate

MODULES = {
    'materials': '原料入库',
    'production': '客户工艺',
    'consumption': '用纱核算',
    'delivery': '送货记录',
    'finance': '财务管理',
    'wages': '工资管理',
}

app = create_app('development')

with app.app_context():
    db.create_all()
    print('✅ 数据库表创建成功！')

    admin = User.query.filter_by(username='admin').first()
    if admin is None:
        admin = User(
            username='admin',
            display_name='系统管理员',
            role='admin',
            is_active_user=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('✅ 默认管理员账号创建成功！')
        print('   用户名: admin / 密码: admin123')
        print('   ⚠️  请登录后立即修改密码！')
    else:
        print('ℹ️  管理员账号已存在，跳过创建')

    rate_count = WageRate.query.count()
    if rate_count == 0:
        default_rate = WageRate(
            name='标准整经费率',
            rate=0.05,
            description='默认整经工资费率，每米0.05元',
            is_active=True
        )
        db.session.add(default_rate)
        db.session.commit()
        print('✅ 默认工资费率创建成功')
    else:
        print(f'ℹ️  已有 {rate_count} 条工资费率，跳过创建')

    print('\n🎉 数据库初始化完成！')
