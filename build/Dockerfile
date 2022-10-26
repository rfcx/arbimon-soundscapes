FROM python:3.8-buster AS soundscapes

## Install OS and Python dependencies
ADD requirements.txt /requirements.txt
RUN apt update && \
    pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r /requirements.txt

ARG RFCX_SDK_VERSION=0.2.1
RUN wget https://github.com/rfcx/rfcx-sdk-python/releases/download/${RFCX_SDK_VERSION}/rfcx-${RFCX_SDK_VERSION}-py3-none-any.whl && \
    pip3 install --no-cache-dir /rfcx-${RFCX_SDK_VERSION}-py3-none-any.whl && \
    rm /rfcx-${RFCX_SDK_VERSION}-py3-none-any.whl

ADD build/entrypoint.sh /entrypoint.sh
RUN chmod 700 /entrypoint.sh && mkdir /app
ENTRYPOINT [ "/entrypoint.sh" ]

ARG RFCX_API_URL=https://staging-api.rfcx.org/
ENV RFCX_API_URL=${RFCX_API_URL}

WORKDIR /app
ADD soundscapes soundscapes

CMD ["cli"]
