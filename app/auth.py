from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User
from functools import wraps

bp = Blueprint('auth', __name__)

# 登录
@bp.route('/login', methods=['GET', 'POST'])
def login():

    if 'user_id' in session:
        return redirect(url_for('map.index'))
    
    if request.method == 'POST':
        username = request.form.get('username','')
        password = request.form.get('password','')
        
        if not username or not password:
            flash('请输入用户名和密码！','error')
            return render_template('login.html')
        
        user = User.query.filter(User.username==username).first()

        if user and user.check_password(password):
            session.permanent = True
            session['user_id'] = user.id
            flash('登录成功！','success')
            return redirect(url_for('map.index'))
        else:
            flash('用户名或密码错误！','error')
            return render_template('login.html')
    else:
        return render_template('login.html')
    


# 退出登录
@bp.route('/logout')
def logout():
    session.clear()
    flash('已退出登录！','success')
    return redirect(url_for('auth.login'))

# 检查登录状态
def check_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return wrapper