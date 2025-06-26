FROM python:3.10-slim
WORKDIR /main
COPY /app/requirements.txt /main
RUN pip install -r requirements.txt
COPY /app/. /main/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]