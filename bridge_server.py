#!/usr/bin/env python3
"""
桥梁服务器 — 在本机注册账号，云电脑自动拉取使用。
部署方式：
  1. 本地运行: python bridge_server.py
  2. 用 ngrok 暴露: ngrok http 8766
  3. 部署到 Render.com（免费）: Start Command = "python bridge_server.py"

API:
  POST /upload  {"email":"...","password":"...","token":"..."}  → 上传账号
  GET  /next    → 取下一个待用账号（取后标记已领取）
  GET  /count   → 查看待领取/已领取数量
"""
import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

STORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'accounts.json')


def load_store():
    if not os.path.exists(STORE_FILE):
        return {'pending': [], 'claimed': []}
    with open(STORE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_store(data):
    with open(STORE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0] if args else format}")

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/next':
            data = load_store()
            if not data['pending']:
                self._send_json({'ok': False, 'msg': 'empty'})
                return
            account = data['pending'].pop(0)
            data['claimed'].append({**account, 'claimedAt': int(time.time())})
            save_store(data)
            self._send_json({
                'ok': True,
                'email': account['email'],
                'password': account['password'],
                'token': account.get('token', ''),
            })
        elif path == '/count':
            data = load_store()
            self._send_json({'pending': len(data['pending']), 'claimed': len(data['claimed'])})
        elif path == '/health':
            self._send_json({'ok': True})
        else:
            self._send_json({'error': 'not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/upload':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length)) if length else {}
            except Exception:
                return self._send_json({'ok': False, 'error': 'invalid JSON'}, 400)

            email = body.get('email', '').strip()
            password = body.get('password', '')
            token = body.get('token', '')
            if not email or not password:
                return self._send_json({'ok': False, 'error': 'missing email/password'}, 400)

            data = load_store()
            if any(a['email'] == email for a in data['pending']):
                self._send_json({'ok': True, 'status': 'duplicate'})
                return

            data['pending'].append({
                'email': email,
                'password': password,
                'token': token,
                'uploadedAt': int(time.time()),
            })
            save_store(data)
            print(f"  ✓ 已接收: {email} (待领取: {len(data['pending'])})")
            self._send_json({'ok': True, 'pending': len(data['pending'])})
        else:
            self._send_json({'error': 'not found'}, 404)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8766))
    server = HTTPServer(('0.0.0.0', port), BridgeHandler)
    print(f'Bridge server running on http://0.0.0.0:{port}')
    print(f'  POST /upload  — 上传账号')
    print(f'  GET  /next    — 取账号')
    print(f'  GET  /count   — 查看数量')
    server.serve_forever()
