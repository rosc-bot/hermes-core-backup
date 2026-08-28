import http.server
import socketserver
import os

PORT = 24633
SUB_FILE = "/home/ubuntu/singbox_subs.yaml"
RAW_BASE64 = "/home/ubuntu/raw_base64.txt"

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class SubHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/clash", "/clash.yaml", "/sub.yaml", "/clmi.yaml"]:
            if os.path.exists(SUB_FILE):
                self.send_response(200)
                self.send_header("Content-Type", "text/yaml; charset=utf-8")
                self.send_header("Subscription-Userinfo", "upload=0; download=0; total=10737418240000; expire=2099999999")
                self.end_headers()
                with open(SUB_FILE, "rb") as f:
                    self.wfile.write(f.read())
                return
        elif self.path in ["/sub", "/v2ray", "/base64", "/"]:
            if os.path.exists(RAW_BASE64):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Subscription-Userinfo", "upload=0; download=0; total=10737418240000; expire=2099999999")
                self.end_headers()
                with open(RAW_BASE64, "rb") as f:
                    self.wfile.write(f.read())
                return
        self.send_response(404)
        self.end_headers()

if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), SubHandler) as httpd:
        print(f"Serving subscription on port {PORT}")
        httpd.serve_forever()