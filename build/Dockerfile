FROM python:3.8-buster AS arbimon-soundscapes

# Buster is EOL; redirect apt to the Debian archive so apt-get update works.
RUN set -eux; \
    sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g; s|http://deb.debian.org/debian-security|http://archive.debian.org/debian-security|g; s|http://security.debian.org/debian-security|http://archive.debian.org/debian-security|g' /etc/apt/sources.list; \
    printf 'Acquire::Check-Valid-Until "false";\nAcquire::Retries "5";\n' > /etc/apt/apt.conf.d/99archive

# Install R, sox and libsndfile/libfftw (required by seewave)
RUN apt-get update && \
    apt-get install -y opus-tools sox r-base r-cran-devtools libsndfile-dev libfftw3-3 libfftw3-dev pkg-config

# Install seewave (R package)
ARG SEEWAVE_VERSION=2.2.3
RUN if [ "$SEEWAVE_VERSION" = "latest" ]; then \
        Rscript -e 'install.packages("seewave")'; \
    else \
        Rscript -e "require(devtools); install_version(\"seewave\", version=\"$SEEWAVE_VERSION\", repos=\"https://cran.r-project.org\")"; \
    fi

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
