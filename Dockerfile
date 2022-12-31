FROM ghcr.io/project-osrm/osrm-backend:v5.27.1 AS osrm-docker

RUN apt-get -y update \
    && apt-get -y upgrade \
    && apt-get -y install python3 \
    && apt-get -y install python3-pip
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /app
COPY code/*.py .
COPY code/requirements.txt .
ADD code/testdata ./testdata
RUN python -m pip install --trusted-host pypi.python.org -r requirements.txt

EXPOSE 5000-5010
EXPOSE 8001

CMD ["python", "app.py"]

