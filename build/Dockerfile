FROM python:3.8-buster AS arbimon-soundscapes

# Install R, sox and libsndfile/libfftw (required by seewave)
RUN apt-get update && \
    apt-get install -y sox r-base r-cran-devtools libsndfile-dev libfftw3-3 libfftw3-dev pkg-config

# Install seewave (R package)
ARG SEEWAVE_VERSION=1.7.6
RUN [[ "$SEEWAVE_VERSION" == "latest" ]] && Rscript -e 'install.packages("seewave")' || \
    Rscript -e "require(devtools); install_version(\"seewave\", version=\"$SEEWAVE_VERSION\", repos=\"https://cran.r-project.org\")"

# Install Python dependencies
ADD requirements.txt /requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir autoflake8 flake8 bandit && \
    pip3 install --no-cache-dir -r /requirements.txt

ADD build/entrypoint.sh /entrypoint.sh
RUN chmod 700 /entrypoint.sh && mkdir /app
ENTRYPOINT [ "/entrypoint.sh" ]

ARG RFCX_API_URL=https://staging-api.rfcx.org/
ENV RFCX_API_URL=${RFCX_API_URL}

WORKDIR /app
ADD soundscapes soundscapes

CMD ["cli"]
