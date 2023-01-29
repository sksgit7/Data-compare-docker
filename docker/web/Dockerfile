FROM python:3.7-slim-buster
WORKDIR /app
COPY ./app /app
RUN pip install -r requirements.txt
EXPOSE 3000
CMD python ./app.py