#!/usr/bin/env python3
import socket

from app import create_app

app = create_app()


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "本机IP"


if __name__ == "__main__":
    port = 5001
    host = "0.0.0.0"  # 允许局域网内手机等设备访问
    lan = _lan_ip()
    print("-" * 50)
    print(f"本机访问:   http://127.0.0.1:{port}")
    print(f"局域网访问: http://{lan}:{port}  （手机请用此地址）")
    print("请确保手机与电脑连接同一 WiFi")
    print("-" * 50)
    app.run(host=host, port=port, debug=True)
