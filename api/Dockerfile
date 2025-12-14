FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install flask flask-cors requests
EXPOSE 8080
CMD ["python", "main.py"]
