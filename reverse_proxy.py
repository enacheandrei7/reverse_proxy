import random
import time
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from random import randrange
from itertools import cycle
import socket
import socketserver
import requests
import yaml
import threading

# HOST_NAME = socket.gethostname()
# HOST_IP = socket.gethostbyname(HOST_NAME)
HOST_IP = "127.0.0.1"
PORT = 8081
ADDR = (HOST_IP, PORT)

CLIENT1 = "127.0.0.1:8888"
CLIENT2 = "127.0.0.1:9999"
CLIENT3 = 'https://httpbin.org'
CONFIG_PATH = "./config.yaml"


def tcp_healthcheck():
    """
    interval = check for status each X seconds
    timeout = when checking the health, try for X seconds, if no response -> unhealthy
    :return:
    """
    threading.Timer(15.0, tcp_healthcheck).start()
    print('Printed from outside')


class ReverseProxy(BaseHTTPRequestHandler):
    server_version = "ReverseProxy/1.1"
    protocol_version = 'HTTP/1.0'
    tcp_healthcheck()

    def __init__(self, *args):
        self.config = self.read_yaml(CONFIG_PATH)
        self.services = self.get_services(self.config)
        # self.upstream_srv_list = self.get_upstream_services(self.services)
        self.upstream_srv_list = self.services['hosts']
        self.healthy_upstream_srv = self.upstream_srv_list
        self.load_balancer_type = self.services['lbPolicy']
        self.round_robin_server = cycle(self.healthy_upstream_srv)
        self.sock = self.define_socket()
        # self.tcp_healthcheck()
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        # url = f"{CLIENT3}/get"
        self.round_robin_server = cycle(self.healthy_upstream_srv)
        url = self.select_upstream_service_with_lb(self.load_balancer_type)
        print(self.headers)

        req_header = self.parse_headers()  # header from client
        resp = requests.get(url,
                            headers=req_header,
                            verify=False)  # we pass the header from client to the upstream service and get the response

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

    def round_robin(self, iterator):
        return next(iterator)

    def select_upstream_service_with_lb(self, lb_policy):
        if lb_policy == "ROUND_ROBIN":
            upstream_service = self.round_robin(self.round_robin_server)
            url = f"http://{upstream_service['address']}:{upstream_service['port']}"
            print('URL FROM LB: ', url)
            return url
        else:
            upstream_service = self.upstream_srv_list[randrange(2)]
            url = f"http://{upstream_service['address']}:{upstream_service['port']}"
            return url

    def define_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def tcp_healthcheck(self):
        """
        interval = check for status each X seconds
        timeout = when checking the health, try for X seconds, if no response -> unhealthy
        :return:
        """
        healthcheck_params = self.services['tcpHealthcheck'][0]
        threading.Timer(healthcheck_params['interval'], self.tcp_healthcheck).start()
        self.healthy_upstream_srv = []
        for service in self.upstream_srv_list:
            print('Curr service: ', service)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(healthcheck_params['timeout'])
            # try:
            #     sock.connect((service['address'], service['port']))
                # sock.close()
                # self.healthy_upstream_srv.append(service)
                # print('Ok service: ', service)
            # except TimeoutError:
            #     print('Server has timed out, please try again later.')
            #     print('NOT Ok service: ', service)
            # except socket.error as e:
            #     print('Socket error: ', e)
            #     print('NOT Ok service: ', service)
            # except Exception as e:
            #     print('NOT Ok service: ', service)
            #     print('Another exception occured: ', e)
        # print('Healthy upstream: ', self.healthy_upstream_srv)

    @staticmethod
    def retry_policy():
        print('AAAAAAAAAAAAAAA')

    def read_yaml(self, config_path):
        with open(config_path, "r") as f:
            try:
                config = yaml.load(f, Loader=yaml.FullLoader)
                print(config)
                return config
            except yaml.YAMLError as exc:
                print(exc)
                return

    def get_services(self, config):
        services_dict = config['proxy']['services'][0]
        return services_dict

    def get_upstream_services(self, services_dict):
        print(services_dict)
        upstream_hosts_list = []
        hosts_list = services_dict["hosts"]
        for host in hosts_list:
            upstream_hosts_list.append(f"{host['address']}:{host['port']}")
        # print(upstream_hosts_list)
        return upstream_hosts_list


def main(handler_class=ReverseProxy, server_address=ADDR):
    print('http server is starting on {}:{}...'.format(HOST_IP, PORT))
    web_server = ThreadingHTTPServer(server_address, ReverseProxy)
    print('http server is running as reverse proxy')
    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass

    web_server.server_close()
    print("Server stopped.")


if __name__ == '__main__':
    main()
