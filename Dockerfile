FROM python:3.9.13-alpine
WORKDIR /reverse_proxy
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src src
EXPOSE 8080
ENTRYPOINT ["python", "./src/reverse_proxy.py"]