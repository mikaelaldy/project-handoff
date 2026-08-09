"""Local dev server: serves web/ statically and routes /api/playground to the
real handler. Mirrors what Vercel will do in production."""
import http.server
import importlib.util
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

spec = importlib.util.spec_from_file_location("playground", os.path.join(ROOT, "api", "playground.py"))
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/playground":
            params = urllib.parse.parse_qs(parsed.query)
            event = {"queryStringParameters": {k: v[0] for k, v in params.items()}}
            res = pg.handler(event)
            body = res["body"].encode()
            self.send_response(res["statusCode"])
            for k, v in res["headers"].items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        rel = parsed.path.lstrip("/") or "index.html"
        path = os.path.join(WEB, rel)
        if not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        with open(path, "rb") as f:
            data = f.read()
        CTYPES = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".json": "application/json",
        }
        ctype = CTYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print(f"serving on http://127.0.0.1:{port}  (ctrl-c to stop)")
    httpd.serve_forever()