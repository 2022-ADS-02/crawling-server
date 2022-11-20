FROM python:3.8

COPY ./ /app/
WORKDIR /app

RUN apt-get update
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 7000

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "7000", "main:app"]