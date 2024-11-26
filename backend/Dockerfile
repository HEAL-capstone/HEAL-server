FROM python:3.9-slim

USER root

# Netcat 및 cryptography 빌드를 위한 필수 도구 설치
RUN apt-get update && apt-get install -y \
    iputils-ping \
    curl \
    netcat-openbsd \
    gcc \
    libffi-dev \
    libssl-dev

    
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD ["./wait-for-it.sh", "db", "3306", "--", "python", "app.py"]