from config import GAODE_SERVER_KEY, GAODE_SECURITY_KEY
from urllib.parse import urlencode
from app.utils import generate_sign, safe_str
import requests
from app import db
from app.models import Customer
import pandas as pd
from io import StringIO, BytesIO
from app import utils


def get_customer_paginate(user_id,page=1, per_page=10):
    """获取客户分页数据"""
    pagination = Customer.query.filter_by(owner_id=user_id).paginate(page=page, 
                                                                     per_page=per_page, 
                                                                     error_out=False
                                                                    )
    return pagination



def get_customer_data(user_id):
    """获取当前登录用户的客户数据"""
    customers = Customer.query.filter_by(owner_id=user_id).all()
    return customers
 


def validate_duplicate(name,phone,address,customer_id=None):
    '''验证客户是否存在
        1. 验证客户名称和地址是否重复
        2. 验证客户手机号是否重复
    '''

    errors = []

    if name and address:
        customer = Customer.query.filter(Customer.name==name,Customer.address==address)
        if customer_id:
            customer = customer.filter(Customer.id != customer_id)
        if customer.first():
            errors.append('该客户已存在！姓名和地址相同！') 
        
    if phone:
        customer = Customer.query.filter(Customer.phone==phone)
        if customer_id:
            customer = customer.filter(Customer.id != customer_id)
        if customer.first():
            errors.append('该客户已存在！手机号相同！')
    return errors



def add_customer_data(name, phone, address, user_id):
    """添加客户"""
    if not name or not address:
        raise ValueError("姓名和地址不能为空！")
    if phone and not utils.validate_phone(phone):
        raise ValueError("手机号格式不正确！")
    
    # 验证客户是否存在
    duplicate_errors = validate_duplicate(name,phone,address)
    if duplicate_errors:
        raise ValueError(";".join(duplicate_errors))
    customer = Customer(name=name, 
                        phone=phone or None, 
                        address=address,
                        owner_id=user_id)
    try:
        db.session.add(customer)
        geocode_customer(customer)
        db.session.commit()
        return True	
    except Exception as e:
        db.session.rollback()
        raise e


def edit_customer(customer_id,user_id):
    """跳转至修改客户信息"""

    customer = Customer.query.get(customer_id)
    if not customer:
        return None
    if customer.owner_id != user_id:
        return None

    return customer


def update_customer_data(customer_id, name, phone, address, user_id):
    """修改客户信息"""
    customer = edit_customer(customer_id,user_id)
    if customer is None:
        return None
    # 验证客户是否存在
    duplicate_errors = validate_duplicate(name,phone,address,customer_id)
    if duplicate_errors:
        raise ValueError(",".join(duplicate_errors))


    # 验证手机号是否合法
    if phone and not utils.validate_phone(phone):
        raise ValueError("手机号格式错误！")

        # 如果地址发生变化，重置地理编码状态
    if customer.address != address:
        customer.geocoded_status = None

    # 更新客户信息
    customer.name = name
    customer.phone = phone
    customer.address = address

    try:
        if customer.geocoded_status is None:
            geocode_customer(customer,force=True)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        raise


def delete_customer(customer_id,user_id):
    """删除客户信息"""
    customer = Customer.query.get(customer_id)
    if not customer:
        return False
    if customer.owner_id != user_id:
        return False
    try:
        db.session.delete(customer)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        raise



def search_customer(user_id,keyword=None):
    """搜索客户
        id存字典 避免重复查询数据库获取index
    """
    if not keyword:
        return {
            "customers_data": [],
            "count": 0
        }
    else:
        all_customers = Customer.query.filter(Customer.owner_id == user_id).order_by(Customer.id).all()
        id_to_index = {}
        for i, customer in enumerate(all_customers,start=1):
            id_to_index[customer.id] = i

        customers = Customer.query.filter((Customer.name.contains(keyword)) | 
                                          (Customer.phone.contains(keyword)), 
                                          Customer.owner_id == user_id).order_by(Customer.id).all()
        customers_data = []
        for customer in customers:
            index = id_to_index[customer.id]
            customers_data.append({
                'index': index,
                'customer': customer.to_dict(),
            })
        return {"customers_data": customers_data,
                "count": len(customers)}


# 调用高德地图 API
def geocode_customer(customer, force=False):
    """
    调用高德地图 API 进行地址转坐标。
    """
    print(f"\n=== 开始地理编码: {customer.name} ===")
    print(f"地址: {customer.address}")
    print(f"当前状态: {customer.geocoded_status}")
    print(f"force: {force}")

    # 非强制模式下，如果已经成功获取坐标或有明确错误状态，则不再尝试调用API
    if not force:
        if customer.geocoded_status == '成功' and customer.latitude and customer.longitude:
            return True
        if customer.geocoded_status and customer.geocoded_status not in ['api错误', '请求失败', '未配置密钥']:
            return True

    # 非强制模式下，如果已经有坐标，也不再调用API
    if customer.latitude and customer.longitude and not force:
        customer.geocoded_status = '成功'
        return True
    
    # 强制模式下，如果已经成功获取坐标，则不再尝试调用API
    if force and customer.geocoded_status == '成功' and customer.latitude and customer.longitude:
        return True


    api_key = GAODE_SERVER_KEY
    security_key = GAODE_SECURITY_KEY

    if not api_key:
        customer.geocoded_status = '未配置密钥'
        return False

    # 基础参数
    params = {
        'address': customer.address or '',
        'key': api_key,
        'output': 'json'
    }
    
    # 带密钥请求
    if security_key:
        sig = generate_sign(params, security_key)
        params_with_sig = params.copy()
        params_with_sig['sig'] = sig
        
        # 构建请求URL（需要对参数进行URL编码）
        encoded_params = urlencode(params_with_sig, doseq=True)
        final_url = f"https://restapi.amap.com/v3/geocode/geo?{encoded_params}"
        
        print(f"最终请求URL（签名已屏蔽）: {final_url.replace(sig, '***')}")
        
        try:
            resp = requests.get(final_url, timeout=8)
            print("响应状态码:", resp.status_code)
            print("响应内容:", resp.text[:500])
            
            resp.raise_for_status()
            data = resp.json()

            if str(data.get('status')) == '1' and data.get('geocodes'):
                location = data['geocodes'][0].get('location', '')
                if location:
                    lng, lat = location.split(',')
                    customer.latitude = float(lat)
                    customer.longitude = float(lng)
                    customer.geocoded_status = '成功'
                    return True
                else:
                    customer.geocoded_status = 'api错误：未返回location'
                    return False
            else:
                info = data.get('info', '')
                customer.geocoded_status = f"api错误：{safe_str(info)}"
                return False

        except Exception as e:
            err = safe_str(e)
            print(f"请求异常: {err}")
            customer.geocoded_status = f'请求失败：{err}'
            return False

    else:
        # 没有安全密钥的情况
        encoded_params = urlencode(params, doseq=True)
        final_url = f"https://restapi.amap.com/v3/geocode/geo?{encoded_params}"
        print(f"无签名请求URL: {final_url}")
        
        try:
            resp = requests.get(final_url, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            if str(data.get('status')) == '1' and data.get('geocodes'):
                location = data['geocodes'][0].get('location', '')
                if location:
                    lng, lat = location.split(',')
                    customer.latitude = float(lat)
                    customer.longitude = float(lng)
                    customer.geocoded_status = '成功'
                    return True
            else:
                info = data.get('info', '')
                customer.geocoded_status = f"api错误：{safe_str(info)}"
                return False
                
        except Exception as e:
            err = safe_str(e)
            customer.geocoded_status = f'请求失败：{err}'
            return False

    return False


def try_again_geocode(user_id):
    """重试对失败的客户进行地理编码"""

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
        try:
            if geocode_customer(customer, force=True):
                success_count += 1
                db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"重试客户 {customer.name} 时发生异常: {safe_str(e)}")
    return {
        "total": len(to_retry),
        "success_count": success_count
    }



def read_excel_to_db(file, user_id):
    """
    读取Excel文件，并将客户数据保存到数据库中。
    当前实现说明：
    - 每条数据逐条处理并提交数据库（db.session.commit()）。
    - 每条数据独立调用高德地图 API 进行地理编码。
    - 优点：逻辑简单，易于理解和调试。
    - 缺点：
        1. 性能较低，尤其是数据量较大时（如几千条），逐条提交会导致大量数据库 I/O 开销。
        2. 高德 API 调用频繁，容易触发限流，且无法复用已解析的地址结果。
    
    未来优化方向（适用于大数据量场景）：
    1. 批量提交优化：
        - 将多条数据累积后一次性提交数据库（例如每20条提交一次），减少 commit 次数。
        - 示例伪代码：
            batch_size = 20
            customers_to_add = []
            for customer in customers:
                customers_to_add.append(customer)
                if len(customers_to_add) >= batch_size:
                    db.session.add_all(customers_to_add)
                    db.session.commit()
                    customers_to_add.clear()
    
    2. 缓存机制优化：
        - 引入地址缓存，避免重复调用高德 API。
        - 示例伪代码：
            address_cache = {}
            if customer.address in address_cache:
                lat, lng = address_cache[customer.address]
                customer.latitude = lat
                customer.longitude = lng
            else:
                geocode_customer(customer)
                address_cache[customer.address] = (customer.latitude, customer.longitude)
    
    3. 并发处理优化：
        - 使用多线程或异步方式并发调用高德 API，提高处理速度。
        - 注意控制并发数，避免触发 API 限流。
        - 示例伪代码：
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(geocode_customer_cached, customer) for customer in customers]
                for future in futures:
                    future.result()
    
    4. 技术栈升级：
        - 后续计划重构为 FastAPI 框架，利用其异步特性进一步提升性能。
        - FastAPI 支持 async/await，可结合 aiohttp 实现异步 HTTP 请求。
    
    适用场景：
    - 当前实现适合数据量较小（几百条）的场景。
    - 若数据量超过1000条，建议采用上述优化方案。
    """
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return {
            'code': 1,
            'msg': "文件读取失败,请确保文件格式正确且内容符合要求。",
            'data':None
        }

    # 检查必须存在的列
    required_columns = {'姓名','地址'}
    if not required_columns.issubset(set(df.columns)):
        missing = required_columns - set(df.columns)
        return {
            'code': 1,
            'msg': f"缺少列：{','.join(missing)}",
            'data':None
        }


    success_count = 0
    fail_count = 0
    error_msgs = []
    row_num = 1
    for i, row in df.iterrows():
        row_num  = i + 2 # 加2是因为i从0开始，且Excel第一行是表头 真实数据从第二行开始
        try:
            customer = Customer(
                name=row['姓名'],
                phone=row.get('手机号') or row.get('手机') or row.get('电话') or '', # 手机号列可以是“手机号”或“手机”，如果都没有则默认为空字符串
                address=row['地址'], # 地址必须存在
                owner_id=user_id,
            )
            db.session.add(customer)
            geocode_customer(customer)
            db.session.commit()   # 每条数据单独提交，确保即使部分数据有问题也能保存其他数据
            success_count += 1
        except Exception as e:
            db.session.rollback()
            fail_count += 1
            error_msgs.append(f"第{row_num}行失败: {safe_str(e)}")
        row_num += 1
    return {
        'code': 0,
        'msg': f'成功导入数据{success_count}条数据，失败{fail_count}条数据。',
        'data':{
            "success_count": success_count,
            "fail":fail_count,
            "errors": error_msgs
        }
    }


# 导出数据
'''根据用户ID导出客户数据，支持CSV、XLSX和XLS格式
 当前实现说明：
    - 查询当前用户的所有客户数据并构建DataFrame。
    - 根据指定格式（CSV/XLSX/XLS）将数据写入内存缓冲区并返回。
    - 优点：逻辑清晰，易于维护；支持多种常见文件格式。
    - 缺点：
        1. 数据量较大时可能导致内存溢出（如导出上万条记录）。
        2. 不支持用户自定义筛选条件（如按时间范围或关键词过滤）。
        3. 未对导出过程进行异步处理，可能影响性能。
        4. 缺乏导出进度反馈机制，用户体验较差。

    未来优化方向（适用于大数据量或复杂需求场景）：

    1. 分页导出优化：
        - 对大数据量采用分页查询方式，避免一次性加载所有数据到内存。
        - 示例伪代码：
            page = 1
            per_page = 1000
            while True:
                customers = Customer.query.filter_by(owner_id=user_id).paginate(page=page, per_page=per_page)
                if not customers.items:
                    break
                # 处理当前页数据
                process_customers(customers.items)
                page += 1

    2. 流式响应支持：
        - 使用流式写入技术（如生成器）逐步输出文件内容，降低内存占用。
        - 示例伪代码：
            def generate_csv_stream(customers):
                yield "姓名,手机号,地址\\n"
                for customer in customers:
                    yield f"{customer.name},{customer.phone},{customer.address}\\n"

            return StreamingResponse(generate_csv_stream(customers), media_type="text/csv")

    3. 用户自定义筛选条件：
        - 支持用户传入筛选参数（如起止日期、客户名称关键词等）。
        - 示例伪代码：
            filters = {
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'keyword': '张三'
            }
            query = Customer.query.filter_by(owner_id=user_id)
            if filters.get('start_date'):
                query = query.filter(Customer.created_at >= filters['start_date'])
            if filters.get('keyword'):
                query = query.filter(Customer.name.contains(filters['keyword']))

    4. 异步处理与性能优化：
        - 结合FastAPI框架，使用异步数据库查询和文件写入提升性能。
        - 示例伪代码：
            async def async_output_excel(format, user_id):
                customers = await db.execute(select(Customer).where(Customer.owner_id == user_id))
                ...

    5. 文件压缩与传输优化：
        - 对大文件自动启用压缩（如ZIP格式），减少传输时间和存储空间。
        - 示例伪代码：
            import zipfile
            with zipfile.ZipFile(output_zip, 'w') as zf:
                zf.writestr("customers.csv", csv_content)
    
    适用场景：
    - 当前实现适合数据量较小（几百条以内）且无需高级筛选功能的场景。
    - 若需处理上千条数据或支持复杂筛选，建议采用上述优化方案。

'''
def output_excel(format,user_id):
    customers = Customer.query.filter_by(owner_id=user_id).all()
    data = []
    for c in customers:
        data.append(
            {
                '姓名': c.name,
                '手机号': c.phone or '',
                '地址': c.address,
            }
        )
    df = pd.DataFrame(data)

    if format == 'csv':
        output = StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return output
    elif format == 'xlsx':
        output = BytesIO()
        df.to_excel(output, index=False,engine='openpyxl')
        output.seek(0)
        return output
    elif format == 'xls':
        output = BytesIO()
        df.to_excel(output, index=False,engine='xlwt')
        output.seek(0)
        return output
    else:
        return None
