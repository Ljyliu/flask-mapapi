'''
创建账户脚本
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