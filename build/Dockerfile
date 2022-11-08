FROM python:3.8-buster AS soundscapes

# Install R, sox
RUN apt update && \
    apt install -y r-base sox && \
    Rscript -e 'install.packages("seewave")'
# Install R, sox - use old version of seewave (matching arbimon-jobs)  
# RUN apt update && \
#     apt install -y r-base sox r-cran-devtools libsndfile-dev fftw3 fftw3-dev pkg-config && \
#     Rscript -e 'require(devtools); install_version("seewave", version="1.7.6", repos="https://cran.r-project.org")'

## Install Python dependencies
ADD requirements.txt /requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && \
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
