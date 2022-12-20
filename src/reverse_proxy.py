from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from random import randrange
from itertools import cycle
from requests.adapters import HTTPAdapter, Retry
import socket
import requests
import yaml
import threading

# HOST_NAME = socket.gethostname()
# HOST_IP = socket.gethostbyname(HOST_NAME)

CONFIG_PATH = "./src/config.yaml"


def read_yaml(config_path):
    """
    Method for reading the yaml config file
    Args:
        config_path (Path): Relative path to the yaml file
    Returns:
        config (dict)
    """
    with open(config_path, "r") as f:
        try:
            config = yaml.load(f, Loader=yaml.FullLoader)
            return config
        except yaml.YAMLError as exc:
            print(exc)
            return


def get_services(config):
    """
    Method for reading the services part of the configuration
    Args:
        config (dict): The configuration dictionary
    Returns:
        services_dict (dict)
    """
    services_dict = config['proxy']['services'][0]
    return services_dict


def tcp_healthcheck(healthy_upstr_srv, services):
    """
    Method that verifies the TCP Healthcheck of the connected services, it runs on async sockets, parallel with the main program, veryfing each service at a number of seconds specified in the config file.
    Args:
        healthy_upstr_srv (list): The healthy upstream servers
        services(dict): Dict of services taken from configuration
    Returns:
        healthy_upstr_srv (list)
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
        except socket.error:
            if service in healthy_upstr_srv:
                healthy_upstr_srv.remove(service)
            if service not in unhealthy_upstr_srv:
                unhealthy_upstr_srv.append(service)
        except Exception:
            if service in healthy_upstr_srv:
                healthy_upstr_srv.remove(service)
            if service not in unhealthy_upstr_srv:
                unhealthy_upstr_srv.append(service)
    print('Healthy upstream: ', healthy_upstr_srv)
    print('Unhealthy upstream: ', unhealthy_upstr_srv)

    my_thread = threading.Timer(interval=healthcheck_params['interval'],
                                function=tcp_healthcheck,
                                args=(healthy_upstr_srv, services, ))
    my_thread.daemon = True
    my_thread.start()


class ReverseProxy(BaseHTTPRequestHandler):
    """
    The main class of this program, is used to create the HTTP server and  all the needed methods. It accepts HTTP 1.1 requests.
    """
    server_version = "ReverseProxy/1.1"
    protocol_version = 'HTTP/1.1'
    config = read_yaml(CONFIG_PATH)
    services = get_services(config)
    upstream_srv_list = services['hosts']
    healthy_upstream_srv = []
    tcp_healthcheck(healthy_upstream_srv, services)
    round_robin_server = cycle(upstream_srv_list)
    load_balancer_type = services['lbPolicy']

    def __init__(self, *args):
        """
        Base constructor for the class.
        """
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        """
        Get method for the reverse proxy. It triggers the GET method for the upstream servers, verifies if the host is
        the one specified in configuration, checks if the servers are running, then connect to one of the healthy
        servers using a load balancer that accepts ROUND_ROBIN or RANDOM configurations.
        """
        if self.headers['host'] == self.services['domain']:
            if not self.healthy_upstream_srv:
                resp = "<p>Sorry, no servers available</p>"
                self.send_response(500)
                self.send_header("Content-type", "text/html")
                self.send_header("Content-length", str(len(resp)))
                self.end_headers()
                self.wfile.write(bytes(resp, "utf-8"))
            else:
                curr_service = self.select_upstream_service_with_lb(self.load_balancer_type)
                url = f"http://{curr_service['address']}:{curr_service['port']}"
                req_header = self.parse_headers()  # header from client
                retry_policy = curr_service['retryPolicy'][0]

                s = requests.Session()
                retry = Retry(total=retry_policy['retries'])
                adapter = HTTPAdapter(max_retries=retry)
                s.trust_env = False
                s.mount('http://', adapter)
                s.mount('https://', adapter)

                try:
                    response = s.get(url, headers=req_header, verify=False, timeout=retry_policy['timeout'])
                    self.send_resp_from_upstream(response)
                except requests.exceptions.MissingSchema as err:
                    resp = "<p>Problem with server</p>"
                    self.send_response(500)
                    self.send_header("Content-type", "text/html")
                    self.send_header("Content-length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(bytes(resp, "utf-8"))
                except requests.exceptions.ConnectionError as err:
                    print('Network or URL Problem: ' + str(err))
                    resp = "<p>Problem with server</p>"
                    self.send_response(500)
                    self.send_header("Content-type", "text/html")
                    self.send_header("Content-length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(bytes(resp, "utf-8"))
        else:
            resp = "<p>You are not authorized. Host not 'my-service.my-company.com'</p>"
            self.send_response(401)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-length", str(len(resp)))
            self.end_headers()
            self.wfile.write(bytes(resp, "utf-8"))

    # def do_POST(self):
    #     req_header = self.parse_headers()
    #     if self.headers['Content-length']:
    #         content_length = int(self.headers['content-length'])
    #         post_body = self.rfile.read(content_length)
    #     else:
    #         post_body = {}
    #     resp = requests.post(url, data=post_body, headers=req_header, verify=False)
    #
    #     self.send_resp_from_upstream(resp)

    def parse_headers(self):
        """
        Creates a dictionary with all the received headers.
        Returns:
            req_header (dict)
        """
        req_header = {}
        for key in self.headers:
            req_header[key] = self.headers[key]
        return req_header

    def send_resp_from_upstream(self, response):
        """
        Send the reponse from the upstream server to the client via the proxy.
        Args:
            Response (response): The response from the upstream server
        """
        self.send_response(response.status_code)
        self.send_resp_headers(response)
        self.wfile.write(response.content)

    def send_resp_headers(self, resp):
        """
        Takes the headers received from upstream service and sends it to the client.
        Args:
            resp (response): The response from the upstream server
        """
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

    @staticmethod
    def round_robin(iterator):
        """
        Generates the enxt value of the iretator created from the upstream servers.
        Args:
            iterator (iterator): The iterator generated from the upstream servers
        """
        return next(iterator)

    def select_upstream_service_with_lb(self, lb_policy):
        """
        Select the next upstream server for the connection via load balancer using one of the 2 methods, ROUND_ROBIN or RANDOM.
        Args:
            lb_policy (str): The loud balancer policy from config.
        """
        if lb_policy == "ROUND_ROBIN":
            upstream_service = self.round_robin(self.round_robin_server)
            if upstream_service in self.healthy_upstream_srv:
                return upstream_service
            else:
                while upstream_service not in self.healthy_upstream_srv:
                    upstream_service = self.round_robin(self.round_robin_server)
                return upstream_service
        else:
            num_available_srv = len(self.healthy_upstream_srv)
            upstream_service = self.healthy_upstream_srv[randrange(num_available_srv)]
            return upstream_service

    @staticmethod
    def define_socket():
        """
        Define the characteristics of the socket used for tcp healthchecks.
        Return:
            sock (socket)
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock


def main(handler_class=ReverseProxy):
    """
    Main class used to run the script. It runs the host and the port IP from the configuration file, then starts the server.
    """
    config = read_yaml(CONFIG_PATH)
    host_details = config['proxy']['listen']
    # HOST_IP = host_details['address']
    PORT = host_details['port']
    hostname = socket.gethostname()
    HOST_IP = socket.gethostbyname(hostname)
    print('http server is starting on {}:{}...'.format(HOST_IP, PORT))
    web_server = ThreadingHTTPServer((HOST_IP, PORT), handler_class)
    print('http server is running as reverse proxy')
    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass

    web_server.server_close()
    print("Server stopped.")


if __name__ == '__main__':
    main()
