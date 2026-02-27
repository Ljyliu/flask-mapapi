from config import GAODE_SERVER_KEY, GAODE_SECURITY_KEY
from urllib.parse import urlencode
from app.utils import generate_sign, safe_str
import requests
from app import db

def validate_duplicate(name,phone,address,customer_id=None):
    '''验证客户是否存在
        1. 验证客户名称和地址是否重复
        2. 验证客户手机号是否重复
    '''

    from app.models import Customer

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
