from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

HOST = "127.0.0.1"
PORT = 8888
ADDR = (HOST, PORT)


class ReverseProxy(BaseHTTPRequestHandler):
    server_version = "Client2/1.1"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<p>I am CLIENT 2</p>", "utf-8"))
        print(self.headers)

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        print(self.headers)



def main():
    print('http server is starting on {} port {}...'.format(HOST, PORT))
    web_server = HTTPServer((HOST, PORT), ReverseProxy)
    print('http server is running as reverse proxy')
    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass

    web_server.server_close()
    print("Server stopped.")


if __name__ == '__main__':
    main()
    # resp = requests.get("http://127.0.0.1:8081", verify=False)