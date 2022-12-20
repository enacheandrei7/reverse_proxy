# Reverse_proxy
Example of a reverse proxy server created in python, having also integrated a load balancer that can be switched between RANDOM and ROUND_ROBIN.
The reverse proxy redirects the client's request to one of the available upstream services.

* The reverse proxy sits between multiple clients and one or serveral instances of an upstream service.
* The reverse proxy should support multiple upstream services with multiple instances
* Upstream services are identified using the “Host” HTTP header
* The reverse proxy should implement the following flow:

    1. It listens on HTTP requests and forwards them to one of the instances of an upstream service that will process the requests.
    2. Requests are load-balanced between the instances of an upstream service and the proxy must support multiple load-balancing strategies
    3. After processing the request, the upstream service will respond with the HTTP response back to the reverse proxy
    4. The reverse proxy forwards the response back to the client (downstream) making the request.

* The reverse proxy will support HTTP 1.1
* The reverse proxy should be configured using a YAML configuration file
* In order to be able to get any informations, the user must have the "Host" field in the header set to "my-service.my-company.com"

## To run the program:

1. Clonse the repo:
  `> git clone https://github.com/enacheandrei7/reverse_proxy.git`
2. Enter the project:
  `> cd reverse_proxy`
3. Create a virtual environment
  `> python -m venv venv`
4. Activate the venv and install the requirements
  `> venv/activate/Scripts.bat`
  `> (venv) pip install -r requirements.txt`
5. **For simple utilisation (CHANGE THE PORTS WHERE NEEDED):**
  - Change the config path from './src/config.yaml' to './config.yaml', if port 8080 is already used, change it to other
    (maybe 8081), change the ports from the clients (upstream services) from 9090 to other ports, change these values 
    in the config.yaml too so the app knows where to redirect
  - `> python ./src/reverse_proxy.py`
  - `> python ./client_1/client1.py`
  - `> python ./client_2/client2.py`
  - `> python ./client_3/client3.py`
6. **Utilize with docker (CHANGE THE PORTS WHERE NEEDED):**
  - `> docker network create --subnet=10.1.0.5/16 mynetwork`
  - `> docker build -t client1 -f Dockerfile_client_1 .`
  - `> docker run --net mynetwork --ip 10.1.0.6 -d -p 1111:9090 --name client1 client1`
  - `> docker build -t client2 -f Dockerfile_client_2 .`
  - `> docker run --net mynetwork --ip 10.1.0.7 -d -p 2222:9090 --name client2 client2`
  - `> docker build -t client3 -f Dockerfile_client_3 .`
  - `> docker run --net mynetwork --ip 10.1.0.8 -d -p 3333:9090 --name client3 client3`
  - `> docker build -t reverse_proxy -f Dockerfile_rev_proxy .`
  - `> docker run --net mynetwork -d -p 81:8080 --name rev_proxy reverse_proxy`
7. **Utilize with docker compose:**
  - `> docker-compose build`
  - `> docker-compose up -d`
  - `THE CONTAINERS RUN IN THE SAME CUSTOM NETWORK reverse_proxy_mynetwork AND HAVE STATIC IPV4 ADDRESSES`