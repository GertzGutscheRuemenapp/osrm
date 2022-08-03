FROM osrm/osrm-backend AS osrm-docker

RUN apt-get -y update \
    && apt-get -y upgrade \
    && apt-get -y install python3 \
    && apt-get -y install python3-pip
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /app
COPY requirements.txt .
COPY app.py .
RUN python -m pip install --trusted-host pypi.python.org -r requirements.txt

EXPOSE 5000-5010
EXPOSE 80

CMD ["python", "app.py"]

