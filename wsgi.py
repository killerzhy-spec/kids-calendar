"""WSGI 入口，供 gunicorn 等生产服务器使用。

示例启动命令：
    gunicorn -w 2 -b 0.0.0.0:5001 wsgi:app
"""
from app import app

if __name__ == "__main__":
    app.run()
