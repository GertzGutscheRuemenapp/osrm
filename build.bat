@echo off
REM Script that builds or rebuilds the container image using the Dockerfile and requirements.txt
REM Do not move, rename, or delete this file
docker build --tag=osrm-flask . %*
