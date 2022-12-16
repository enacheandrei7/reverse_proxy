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


def read_yaml(config_path):
    with open(config_path, "r") as f:
        try:
            config = yaml.load(f, Loader=yaml.FullLoader)
            print(config)
            return config
        except yaml.YAMLError as exc:
            print(exc)
            return


def get_services(config):
    services_dict = config['proxy']['services'][0]
    return services_dict


def tcp_healthcheck(healthy_upstr_srv, services):
    """
    interval = check for status each X seconds
    timeout = when checking the health, try for X seconds, if no response -> unhealthy
    :return:
    """
    healthcheck_params = services['tcpHealthcheck'][0]  # interval, timeout
    upstream_services = services['hosts']  # list of upstream services dictionaries
    unhealthy_upstr_srv = []

    for service in upstream_services:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(healthcheck_params['timeout'])
        try:
            sock.connect((service['address'], service['port']))
            sock.close()
            if service not in healthy_upstr_srv:
                healthy_upstr_srv.append(service)
            if service in unhealthy_upstr_srv:
                unhealthy_upstr_srv.remove(service)
        except TimeoutError:
            if service in healthy_upstr_srv:
                healthy_upstr_srv.remove(service)
            if service not in unhealthy_upstr_srv:
                unhealthy_upstr_srv.append(service)
            print(f"Server has timed out, please try again later. Service: {service['address']}:{service['port']}")
        except socket.error as e:
            if service in healthy_upstr_srv:
                healthy_upstr_srv.remove(service)
            if service not in unhealthy_upstr_srv:
                unhealthy_upstr_srv.append(service)
            print('Socket error, service not available: ', e, f"Service: {service['address']}:{service['port']}")
        except Exception as e:
            if service in healthy_upstr_srv:
                healthy_upstr_srv.remove(service)
            if service not in unhealthy_upstr_srv:
                unhealthy_upstr_srv.append(service)
            print('Exception occured, please try again later: ', e)
    print('Healthy upstream: ', healthy_upstr_srv)
    print('Unhealthy upstream: ', unhealthy_upstr_srv)

    my_thread = threading.Timer(interval=healthcheck_params['interval'],
                                function=tcp_healthcheck,
                                args=(healthy_upstr_srv, services, ))
    my_thread.daemon = True
    my_thread.start()



class ReverseProxy(BaseHTTPRequestHandler):
    server_version = "ReverseProxy/1.1"
    protocol_version = 'HTTP/1.0'
    config = read_yaml(CONFIG_PATH)
    services = get_services(config)
    upstream_srv_list = services['hosts']
    healthy_upstream_srv = []
    # dummy_healthy_srv_list = upstream_srv_list.copy()
    tcp_healthcheck(healthy_upstream_srv, services)

    def __init__(self, *args):
        # self.test = self.healthy_upstream_srv  # this was ok, we can return to this
        self.load_balancer_type = self.services['lbPolicy']
        self.round_robin_server = cycle(self.healthy_upstream_srv)
        self.sock = self.define_socket()
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        # url = f"{CLIENT3}/get"
        if not self.healthy_upstream_srv:
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<p>Sorry, no servers available</p>", "utf-8"))
        else:
            # self.round_robin_server = cycle(self.healthy_upstream_srv)
            url = self.select_upstream_service_with_lb(self.load_balancer_type)

            print('THIS IS FROM GET: ', self.test)

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
            num_available_srv = len(self.healthy_upstream_srv)
            upstream_service = self.healthy_upstream_srv[randrange(num_available_srv)]
            url = f"http://{upstream_service['address']}:{upstream_service['port']}"
            return url

    def define_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    @staticmethod
    def retry_policy():
        print('AAAAAAAAAAAAAAA')

    # def get_upstream_services(self, services_dict):
    #     print(services_dict)
    #     upstream_hosts_list = []
    #     hosts_list = services_dict["hosts"]
    #     for host in hosts_list:
    #         upstream_hosts_list.append(f"{host['address']}:{host['port']}")
    #     print(upstream_hosts_list)
    #     return upstream_hosts_list


def main(handler_class=ReverseProxy, server_address=ADDR):
    print('http server is starting on {}:{}...'.format(HOST_IP, PORT))
    web_server = ThreadingHTTPServer(server_address, handler_class)
    print('http server is running as reverse proxy')
    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass

    web_server.server_close()
    print("Server stopped.")


if __name__ == '__main__':
    main()
