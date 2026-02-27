import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()


# 高德地图API密钥
GAODE_SERVER_KEY = os.getenv('GAODE_SERVER_KEY')
GAODE_SECURITY_KEY = os.getenv('GAODE_SECURITY_KEY')
GAODE_WEB_KEY = os.getenv('GAODE_WEB_KEY')
GAODE_SECURITY_CODE = os.getenv('GAODE_SECURITY_CODE')

# db
SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# session
SECRET_KEY = os.getenv('SECRET_KEY')
PERMANENT_SESSION_LIFETIME = timedelta(days=7)
