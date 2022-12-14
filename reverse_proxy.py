from http.server import HTTPServer, BaseHTTPRequestHandler
from random import randrange
from itertools import cycle
import socket
import requests
import yaml

HOST_NAME = socket.gethostname()
HOST_IP = socket.gethostbyname(HOST_NAME)
# HOST_IP = "127.0.0.1"
PORT = 8081
ADDR = (HOST_IP, PORT)

CLIENT1 = "127.0.0.1:8888"
CLIENT2 = "127.0.0.1:9999"
CLIENT3 = 'https://httpbin.org'
CONFIG_PATH = "./config.yaml"


def read_yaml(config_path):
    with open(config_path, "r") as f:
        try:
            config = yaml.load(f, Loader=yaml.FullLoader)
        except yaml.YAMLError as exc:
            print(exc)
            return
    return config


def get_services(config):
    services_dict = config['proxy']['services'][0]
    return services_dict


def get_upstream_services(services_dict):
    print(services_dict)
    upstream_services_list = []
    hosts_list = services_dict["hosts"]
    for host in hosts_list:
        upstream_services_list.append(f"{host['address']}:{host['port']}")
    print(upstream_services_list)
    return upstream_services_list



class ReverseProxy(BaseHTTPRequestHandler):
    server_version = "ReverseProxy/1.1"
    protocol_version = 'HTTP/1.1'
    config = read_yaml(CONFIG_PATH)
    services = get_services(config)
    client_list = get_upstream_services(services)
    load_balancer_type = services['lbPolicy']
    round_robin_server = cycle(client_list)

    def do_GET(self):

        url = f"{CLIENT3}/get"
        # url = self.select_upstream_service_with_lb(self.load_balancer_type)

        # self.headers is the header from client
        req_header = self.parse_headers()
        # here we pass the header from client to the upstream service and get the response
        resp = requests.get(url, headers=req_header, verify=False)

        self.send_resp_from_upstream(resp)


    def do_POST(self):
        url = f"{CLIENT3}/post"
        req_header = self.parse_headers()
        if self.headers['Content-length']:
            content_length = int(self.headers['content-length'])
            post_body = self.rfile.read(content_length)
        else:
            post_body = {}
        resp = requests.post(url, data=post_body, headers=req_header, verify=False)

        self.send_resp_from_upstream(resp)

    def parse_headers(self):
        req_header = {}
        for key in self.headers:
            req_header[key] = self.headers[key]
        return req_header

    def send_resp_from_upstream(self, response):
        self.send_response(response.status_code)
        self.send_resp_headers(response)
        self.wfile.write(response.content)

    def send_resp_headers(self, resp):
        resp_headers = resp.headers
        for key in resp_headers:
            if key not in ['Content-Encoding', 'Transfer-Encoding', 'content-encoding', 'transfer-encoding',
                           'content-length', 'Content-Length']:
                self.send_header(key, resp_headers[key])
        if resp.content:
            self.send_header("Content-length", str(len(resp.text)))
        else:
            self.send_header("Content-length", '0')
        self.end_headers()

    def round_robin(self, iter):
        return next(iter)

    def select_upstream_service_with_lb(self, lb_policy):
        if lb_policy == "ROUND_ROBIN":
            curr_upstream_service = self.round_robin(self.round_robin_server)
            url = f"http://{curr_upstream_service}"
            return url
        else:
            curr_upstream_service = self.client_list[randrange(2)]
            url = f"http://{curr_upstream_service}"
            return url


def main(handler_class=ReverseProxy, server_address=ADDR):
    print('http server is starting on {} port {}...'.format(HOST_IP, PORT))
    web_server = HTTPServer(server_address, handler_class)
    print('http server is running as reverse proxy')
    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass

    web_server.server_close()
    print("Server stopped.")


if __name__ == '__main__':
    main()
