import re
import hashlib
import os
from werkzeug.utils import secure_filename

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


ALLOWED_EXTENSIONS = {'xls', 'xlsx', 'csv'}
ALLOWED_MIME_TYPES = {
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'text/csv'  # .csv
    }

def allowed_file(filename):
    # 判断文件后缀是否在允许的集合中
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def validate_file(file):
    """验证上传的文件是否合法"""

    # 验证文件名
    if not secure_filename(file.filename):
        return False, '文件名包含非法字符'
    
    # 判断文件类型是否在允许的集合中
    if file.content_type not in ALLOWED_MIME_TYPES:
        return False, '不支持的文件类型'
    
    # 判断文件后缀是否在允许的集合中
    if not allowed_file(file.filename):
        return False, '不支持的文件类型'
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    file.seek(0, os.SEEK_END)  # 移动到文件末尾
    file_size = file.tell()  # 获取文件大小
    file.seek(0)  # 重置文件指针到开头
    
    if file_size > MAX_FILE_SIZE:
        return False, '文件过大，最大支持10MB'
    
    return True, '文件校验成功'