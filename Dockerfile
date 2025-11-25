FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install flask boto3

EXPOSE 5000

CMD ["python3", "app.py"]
