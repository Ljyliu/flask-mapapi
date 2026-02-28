from config import GAODE_SERVER_KEY, GAODE_SECURITY_KEY
from urllib.parse import urlencode
from app.utils import generate_sign, safe_str
import requests
from app import db
from app.models import Customer
import pandas as pd
from io import StringIO, BytesIO


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
                phone=row.get('手机号') or row.get('手机') or '', # 手机号列可以是“手机号”或“手机”，如果都没有则默认为空字符串
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
