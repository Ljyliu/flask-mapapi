import re
import hashlib

# 工具类 用于处理成字符串
def safe_str(value, default="未知错误"):
    if value is None:
        return default
    
    # 处理嵌套列表（有可能是双重列表）
    while isinstance(value, list) and len(value) == 1 and isinstance(value[0], (list, tuple)):
        value = value[0]
    
    # 递归处理列表元组
    if isinstance(value, (list, tuple)):
        return " | ".join(safe_str(item, default) for item in value)
    
    # 处理字典
    if isinstance(value, dict):
        return " | ".join(f"{safe_str(k)}:{safe_str(v)}" for k, v in value.items())
    
    return str(value)


def validate_phone(phone):
    '''验证手机号是否合法
    1. 允许空手机号
    2. 不为空时验证手机号格式是否正确
    '''
    if not phone:
        return True
    phone = phone.strip()
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern,phone))

def validate_customer(name,address):
    '''验证客户信息'''
    errors = []
    if not name:
        errors.append('姓名不能为空！')
    if not address:
        errors.append('地址不能为空！')
    return errors


# 生成签名
def generate_sign(params, security_key):
    # 参数排序
    sorted_items = sorted(params.items(), key=lambda x: x[0])
    # 生成字符串：key1=value1&key2=value2
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_items])
    # 添加私钥
    string_to_sign = query_string + security_key
    # MD5加密
    sign = hashlib.md5(string_to_sign.encode('utf-8')).hexdigest()
    return sign
