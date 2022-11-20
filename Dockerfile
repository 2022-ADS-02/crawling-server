FROM python:3.8

COPY ./ /app/
WORKDIR /app

RUN apt-get update
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 7001

ENV TZ Asia/Seoul

CMD ["python", "main.py"]