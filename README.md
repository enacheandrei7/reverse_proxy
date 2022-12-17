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


