from app import db
from app.models import Customer
from config import GAODE_WEB_KEY, GAODE_SECURITY_CODE
from flask import render_template, request, redirect, url_for, jsonify, session
from app.auth import check_login
from app.utils import validate_phone, validate_customer, safe_str
from flask import Blueprint
from app.service import validate_duplicate, geocode_customer

bp = Blueprint('map', __name__)

# 首页加地图
@bp.route('/')
@check_login
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('index.html',
                            web_key=GAODE_WEB_KEY,
                            s_code=GAODE_SECURITY_CODE)

# 客户列表
@bp.route('/customers/')
@check_login
def list_customers():
    customers = Customer.query.paginate(
        page=request.args.get('page',1,type=int),
        per_page=10,
        error_out=False
    )
    return render_template('customers.html',customers=customers)


# 客户数据 json 
@bp.route('/customers/data')
@check_login
def customers_data():
    # 获取当前登录用户的客户数据 校验
    user_id = session.get('user_id')
    customers = Customer.query.filter_by(owner_id=user_id).all()
    return jsonify([customer.to_dict() for customer in customers])

# 重试编码
@bp.route('/geocode/retry', methods=['POST'])
@check_login
def retry_geocode():
    """重新尝试对失败的客户进行地理编码"""
    try:
        user_id = session.get('user_id')
        # 查找所有需要重试的客户
        to_retry = Customer.query.filter(
            Customer.owner_id == user_id,
            (Customer.geocoded_status.is_(None)) |
            (Customer.geocoded_status == '已存在坐标') |
            (Customer.geocoded_status == '未配置密钥') |
            (Customer.geocoded_status.startswith('api错误')) |
            (Customer.geocoded_status.startswith('请求失败'))
        ).all()
        
        success_count = 0
        for customer in to_retry:
            # 强制重新获取坐标
            if geocode_customer(customer, force=True):
                success_count += 1
        
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"成功修复 {success_count} 个客户坐标",
            "total": len(to_retry),
            "success_count": success_count
        })
    except Exception as e:
        db.session.rollback()
        # 关键修复：使用safe_str处理异常
        error_msg = safe_str(e)
        return jsonify({
            "status": "error",
            "message": f"处理失败: {error_msg}"
        }), 500


# 点击添加客户 GET 跳转到添加客户页
@bp.route('/customers/add/',methods=['GET'])
@check_login
def add():
    return render_template('add.html')



# 添加客户 POST 获得新客户信息保存到数据库，并跳转到客户列表页
@bp.route('/customers/add_customers/',methods=['POST'])
@check_login
def add_customers():

    user_id = session.get('user_id')
    # 获取新客户信息
    cname = request.form.get('name','').strip()
    cphone = request.form.get('phone','').strip()
    caddress = request.form.get('address','').strip()
    
    # 验证手机号是否合法
    if cphone and not validate_phone(cphone):
        return '手机号不正确！请输入11位有效手机号',400
    
    # 验证客户信息
    errors = validate_customer(cname,caddress)
    if errors:
        return ','.join(errors),400
    
    # 验证客户是否存在
    duplicate_errors = validate_duplicate(cname,cphone,caddress)
    if duplicate_errors:
        return ','.join(duplicate_errors),400
    
    
    # 创建新客户数据并保存到数据库
    try:
        new_customer = Customer(name=cname,phone=cphone or None,address=caddress,owner_id=user_id)
        db.session.add(new_customer)
        geocode_customer(new_customer)
        db.session.commit()
        return redirect(url_for('map.list_customers'))
    except Exception as e:
        db.session.rollback()
        return f'添加客户失败：{str(e)}',500

# 修改客户 GET 跳转到修改客户页
@bp.route('/customers/<int:customer_id>/edit',methods=['GET'])
@check_login
def update_customer(customer_id):
    user_id = session.get('user_id')
    customer = Customer.query.get_or_404(customer_id)
    if customer.owner_id != user_id:
        return "无权访问", 403
    return render_template('edit_update.html',customer=customer)


# 修改客户 POST 获得修改客户信息保存到数据库，并跳转到客户列表页
@bp.route('/customers/<int:customer_id>/update',methods=['POST'])
@check_login
def update(customer_id):
    user_id = session.get('user_id')

    customer = Customer.query.get_or_404(customer_id)
    if customer.owner_id != user_id:
        return "无权访问", 403

    new_name = request.form.get('name','').strip()
    new_phone = request.form.get('phone','').strip()
    new_address = request.form.get('address','').strip()   

    # 如果地址发生变化，重置地理编码状态
    if customer.address != new_address:
        customer.geocoded_status = None


    # 更新客户信息
    customer.name = new_name
    customer.phone = new_phone
    customer.address = new_address

    # 验证手机号是否合法
    if customer.phone and not validate_phone(customer.phone):
        return '手机号不正确！请输入11位有效手机号',400
    
    # 验证客户信息
    errors = validate_customer(customer.name,customer.address)
    if errors:
        return ','.join(errors),400
    
    # 验证客户是否存在
    duplicate_errors = validate_duplicate(customer.name,customer.phone,customer.address,customer_id)
    if duplicate_errors:
        return ','.join(duplicate_errors),400
    
    # 提交更改
    try:
        if customer.geocoded_status is None:
            geocode_customer(customer,force=True)
        db.session.commit()
        return redirect(url_for('map.list_customers'))
    except Exception as e:
        db.session.rollback()
        return f'修改客户信息失败：{str(e)}',500



# 删除客户
@bp.route('/customers/<int:customer_id>/delete',methods=['POST'])
@check_login
def delete(customer_id):
    user_id = session.get('user_id')
    customer = Customer.query.get(customer_id)
    if customer.owner_id != user_id:
        return "无权删除", 403
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('map.list_customers'))


# 搜索客户
@bp.route('/customers/search/')
@check_login
def search():
    keyword = request.args.get('keyword', '').strip()
    user_id = session.get('user_id')
    if not keyword:
        return redirect(url_for('map.list_customers'))
    else:
        customers = Customer.query.filter((Customer.name.contains(keyword)) | (Customer.phone.contains(keyword)), Customer.owner_id == user_id).all()
        customers_data = []
        for customer in customers:
            index = Customer.query.filter(Customer.id < customer.id).count() + 1
            customers_data.append({
                'index': index,
                'customer': customer.to_dict(),
            })
    return render_template('search_results.html',
                            keyword=keyword,
                            count=len(customers),
                            customers_data=customers_data,
                            web_key=GAODE_WEB_KEY,
                            s_code=GAODE_SECURITY_CODE)    