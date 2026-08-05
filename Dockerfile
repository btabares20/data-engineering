FROM apache/airflow:3.3.0
USER root

COPY requirements.txt /requirements.txt
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         vim \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow

RUN pip install --no-cache-dir -r /requirements.txt
COPY src /opt/project/src
