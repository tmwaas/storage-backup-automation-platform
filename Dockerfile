FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install flask boto3
RUN pip install prometheus-client

EXPOSE 5000

CMD ["python3", "app.py"]
