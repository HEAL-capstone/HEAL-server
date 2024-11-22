FROM python:3.9-slim

# Netcat 설치
RUN apt-get update && apt-get install -y netcat-openbsd

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD ["./wait-for-it.sh", "db", "3306", "--", "python", "app.py"]