# Subscription Server Protocols & EOF Troubleshooting

## 1. Why Clients Throw `Get "http://IP:PORT/path": EOF`
When mobile proxy clients (such as Surfing, Mihomo, Clash Verge, Surfboard) request a subscription URL, their HTTP client stack often issues a **`HEAD`** request first (to probe `Content-Length` and `Subscription-Userinfo` bandwidth headers), or requires explicit headers before streaming the payload.

If the subscription server (e.g. a custom Python `http.server` or microservice):
1. Only implements `do_GET` and returns HTTP 501 / closes connection on `HEAD`
2. Does not declare `Content-Length`
3. Keeps the TCP socket in a hanging state without `Connection: close`

The client immediately aborts the handshake with:
```text
Get "http://<IP>:<PORT>/...": EOF
```

## 2. Robust Python Subscription Server Implementation
When running a standalone subscription dispatcher on a VPS, use `BaseHTTPRequestHandler` with unified `HEAD` and `GET` handling, `allow_reuse_address = True`, and proper subscription metadata:

```python
import http.server
import socketserver
import os

PORT = 24633
SUB_FILE = "/path/to/clash_nodes.yaml"
RAW_BASE64 = "/path/to/raw_base64.txt"

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class SubHandler(http.server.BaseHTTPRequestHandler):
    def send_sub_response(self, is_head=False):
        if self.path in ["/clash", "/clash.yaml", "/sub.yaml"]:
            if os.path.exists(SUB_FILE):
                with open(SUB_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/yaml; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Subscription-Userinfo", "upload=0; download=0; total=10737418240000; expire=2099999999")
                self.send_header("Connection", "close")
                self.end_headers()
                if not is_head:
                    self.wfile.write(content)
                return
        elif self.path in ["/sub", "/v2ray", "/base64", "/"]:
            if os.path.exists(RAW_BASE64):
                with open(RAW_BASE64, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Subscription-Userinfo", "upload=0; download=0; total=10737418240000; expire=2099999999")
                self.send_header("Connection", "close")
                self.end_headers()
                if not is_head:
                    self.wfile.write(content)
                return
        self.send_response(404)
        self.end_headers()

    def do_HEAD(self):
        self.send_sub_response(is_head=True)

    def do_GET(self):
        self.send_sub_response(is_head=False)

if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), SubHandler) as httpd:
        httpd.serve_forever()
```

## 3. Base64 VMess Line Truncation & Chat Delivery
When outputting VMess links (`vmess://...` JSON base64 encoded strings) to users over chat platforms like Telegram:
- Very long unbroken alphanumeric strings may be collapsed or truncated by rendering engines or middleware.
- Always provide the full uncompressed text explicitly or deliver via attachment file (`MEDIA:/path/to/vmess.txt`) so the user can import without corrupted base64 blocks.
