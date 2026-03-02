from app import db
from config import GAODE_WEB_KEY, GAODE_SECURITY_CODE
from flask import render_template, request, redirect, url_for, jsonify, session, Response,flash
from app.auth import check_login
from app.utils import safe_str, validate_file
from flask import Blueprint
from app import service

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
    user_id = session.get('user_id')
    page = request.args.get('page',1,type=int)
    customers = service.get_customer_paginate(user_id,page=page)
    return render_template('customers.html',customers=customers)


# 客户数据 json 
@bp.route('/customers/data')
@check_login
def customers_data():
    # 获取当前登录用户的客户数据 校验
    user_id = session.get('user_id')
    customers = service.get_customer_data(user_id)
    return jsonify([customer.to_dict() for customer in customers])

# 重试编码
@bp.route('/geocode/retry', methods=['POST'])
@check_login
def retry_geocode():
    """重新尝试对失败的客户进行地理编码"""
    try:
        user_id = session.get('user_id')
        result = service.try_again_geocode(user_id)
        return jsonify({
            "status": "success",
            "message": f"成功修复 {result['success_count']} 个客户坐标",
            "total": result['total'],
            "success_count": result['success_count']
        })
    except Exception as e:
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
    try:
        service.add_customer_data(cname,cphone,caddress,user_id)
        flash('添加客户成功！')
        return redirect(url_for('map.list_customers'))
    except ValueError as ve:
        flash(f'添加失败：{safe_str(ve)}')
    except Exception as e:
        flash('服务器出现错误，请稍后再试')
    return render_template('add.html')


# 修改客户 GET 跳转到修改客户页
@bp.route('/customers/<int:customer_id>/edit',methods=['GET'])
@check_login
def update_customer(customer_id):
    user_id = session.get('user_id')
    customer = service.edit_customer(customer_id,user_id)
    if customer is None:
        return "无权访问该客户信息！", 403
    return render_template('edit_update.html',customer=customer)


# 修改客户 POST 获得修改客户信息保存到数据库，并跳转到客户列表页
@bp.route('/customers/<int:customer_id>/update',methods=['POST'])
@check_login
def update(customer_id):
    user_id = session.get('user_id')

    new_name = request.form.get('name','').strip()
    new_phone = request.form.get('phone','').strip()
    new_address = request.form.get('address','').strip()   

    
    try:
        result = service.update_customer_data(customer_id,new_name,new_phone,new_address,user_id)
        if result is None:
            flash('无权修改或客户信息不存在，客户信息未修改！')
            return redirect(url_for('map.list_customers'))
        elif result is True:
            flash('客户信息修改成功！')
            return redirect(url_for('map.list_customers'))
        
    except ValueError as ve:
        flash(f'修改失败：{safe_str(ve)}')
        return redirect(url_for('map.update_customer', customer_id=customer_id))

    except Exception as e:
        flash('服务器出现错误，请稍后再试')
        return redirect(url_for('map.update_customer', customer_id=customer_id))



# 删除客户
@bp.route('/customers/<int:customer_id>/delete',methods=['POST'])
@check_login
def delete(customer_id):
    user_id = session.get('user_id')
    success = service.delete_customer(customer_id,user_id)
    if not success:
        return "无权访问或客户不存在！", 403
    return redirect(url_for('map.list_customers'))


# 搜索客户
@bp.route('/customers/search/')
@check_login
def search():
    keyword = request.args.get('keyword', '').strip()
    user_id = session.get('user_id')

    result = service.search_customer(user_id,keyword)

    total = result['count']
    customers_data = result['customers_data']
    return render_template('search_results.html',
                            keyword=keyword,
                            count=total,
                            customers_data=customers_data,
                            web_key=GAODE_WEB_KEY,
                            s_code=GAODE_SECURITY_CODE)


# 导入客户数据
@bp.route('/customers/import/', methods=['POST'])
@check_login
def import_customers():
    user_id = session.get('user_id')

    file = request.files.get('file')
    if not file:
        return jsonify(
            {
                'code': '400',
                'message': '请选择文件',
            }
        ), 400
    
    # 验证文件格式
    is_valid, error_msg = validate_file(file)
    if not is_valid:
        return {
            'code': 1, # 0 表示成功 1 表示失败
            'msg': error_msg,
            'data': None
        }

    # 调用service层的函数处理文件并导入数据
    result = service.read_excel_to_db(file, user_id)
    return jsonify(result)


# 导出客户数据
@bp.route('/customers/export/<format>',methods=['GET'])
@check_login
def export_customers(format):
    user_id = session.get('user_id')
    
    output = service.output_excel(format,user_id)
    if format == 'csv':
        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment;filename=customers.csv'
            }
        )
    elif format == 'xls':
        return Response(
            output,
            mimetype='application/vnd.ms-excel',
            headers={
                'Content-Disposition': f'attachment;filename=customers.xls'
            }
        )
    elif format == 'xlsx':
        return Response(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment;filename=customers.xlsx'
            }
        )
    else:
        return jsonify({
            'code': 400,
            'message': '不支持的格式'
        }), 400
