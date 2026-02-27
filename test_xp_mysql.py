# 测试mysql连接
import MySQLdb
import os
from dotenv import load_dotenv

def test_xp_mysql():
    print("测试mysql连接")
    try:
        load_dotenv()
        config = {
                'host': 'localhost',
                'port': 3306,
                'user': 'root',
                'password': os.getenv('DB_PASSWORD'),
                'database': 'mysql',
            }
            # 第一次测试连接系统数据库
        print("尝试连接MySQL系统数据库...")
        connection = MySQLdb.connect(**config)
        print("连接成功！")

            # 测试查询功能
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        data = cursor.fetchone()
        print(f"MySQL系统数据库版本为: {data[0]}" )

            # 检查数据库是否存在，不存在则创建
        cursor.execute("SHOW DATABASES LIKE 'customer_map'")
        exists = cursor.fetchone()
        if exists:
            print("数据库已存在")
        else:
            print("数据库不存在,开始创建...")
            cursor.execute("CREATE DATABASE customer_map CHARACTER SET utf8mb4")
            print("数据库创建成功")


            # 显示所有数据库 验证是否创建成功
            cursor.execute("SHOW DATABASES")
            databases = [db[0] for db in cursor.fetchall()]
            print(f"所有数据库:{','.join(databases)}")

            # 关闭连接
            cursor.close()
            connection.close()
            print("连接关闭")

    except Exception as e:
            print(f"连接失败: {e}")
            return False

            # 第二次测试连接到刚创建的数据库
    print("\n2.尝试连接customer_map数据库...")
    try:
        config2 = {
                    'host': 'localhost',
                    'port': 3306,
                    'user': 'root',
                    'password': os.getenv('DB_PASSWORD'),
                    'database': 'customer_map',
                }
        conn = MySQLdb.connect(**config2)
        print("customer_map数据库连接成功")
            
            # 测试在customer_map数据库中操作
        cursor2 = conn.cursor()
        cursor2.execute("SHOW TABLES")
        tables = cursor2.fetchall()
        print(f"customer_map数据库中的表: {tables}")

        cursor2.close()
        conn.close()
        print("测试完成，customer_map数据库连接关闭")
        return True

    except Exception as e:
        print(f"customer_map数据库连接失败: {e}")
        return False

        
        

if __name__ == "__main__":
    test_xp_mysql()

