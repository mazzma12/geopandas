FROM python:3.6 

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y libspatialindex-dev gdal-bin libgdal-dev python3-gdal
COPY requirements.test.txt requirements.txt ./
RUN pip3 install -r requirements.test.txt 
RUN pip3 install -r requirements.txt

COPY . . 

RUN python3 setup.py develop
RUN pip3 install notebook
RUN alias jn="jupyter notebook --allow-root --no-browser --ip-0.0.0.0 --port 8889"
ENTRYPOINT ["bash"]
