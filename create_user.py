
'''
创建账户脚本（仅供管理员使用）

说明：
- 此脚本用于后台手动创建用户账号，不对外开放注册功能。
- 主要用于项目演示、测试或初始化管理员账号。
- 不需要复杂的前端界面，简化开发流程。

使用方法：
1. 运行脚本：python create_user.py
2. 按提示输入用户名和密码即可创建账号。
3. 创建成功后，用户可通过登录页面使用该账号登录系统。

注意事项：
- 用户名不能重复。
- 密码需确认两次，确保输入一致。
- 密码将以加密形式存储到数据库中。
'''


from run import app, db, User
import getpass

def create_user():
    with app.app_context():
        username = input("请输入用户名：")
        password = getpass.getpass("请输入密码：")
        password_confirm = getpass.getpass("请确认密码：")

        if password != password_confirm:
            print("两次密码不一致！")
            return

        if User.query.filter_by(username=username).first():
            print("用户已存在！")
            return

        try:
            user = User()
            user.username = username
            user.create_password(password)

            db.session.add(user)
            db.session.commit()
            print(f"用户 {username} 创建成功！")
        except:
            db.session.rollback()
            print("创建失败")

if __name__ == '__main__':
    create_user()