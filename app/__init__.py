from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os


db = SQLAlchemy()
migrate = Migrate()


def create_app():

    # 设置模板目录
    root_path = os.path.dirname(os.path.dirname(__file__))
    template_folder = os.path.join(root_path, 'templates')

    app = Flask(__name__, template_folder=template_folder)

    # 加载配置
    import config
    app.config.from_object(config)

    @app.context_processor
    def inject_user():
        from app.models import User
        user = None
        if 'user_id' in session:
            user = User.query.get(session['user_id'])

        return dict(user=user)

    # 初始化数据库
    db.init_app(app)
    migrate.init_app(app, db)

    # 注册蓝图
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    from app.map import bp as map_bp
    app.register_blueprint(map_bp)

    return app
