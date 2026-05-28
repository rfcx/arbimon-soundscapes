# Build of arbimon-soundscapes. The base
# image python:3.8-buster targets Debian Buster, which is EOL — its repos
# moved to archive.debian.org and the live deb.debian.org mirrors now 404.
# We redirect sources.list to the archive (and disable the Valid-Until
# check, since archive snapshots have stale Release dates) so apt works.
# Toolchain otherwise unchanged (python 3.8, buster R, seewave 1.7.6) to
# preserve numerical-result parity with the legacy jobqueue worker.
#
FROM python:3.8-buster AS arbimon-soundscapes

# Redirect Buster apt to the Debian archive (EOL distro) before installing.
RUN set -eux; \
    sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g; s|http://deb.debian.org/debian-security|http://archive.debian.org/debian-security|g; s|http://security.debian.org/debian-security|http://archive.debian.org/debian-security|g' /etc/apt/sources.list; \
    printf 'Acquire::Check-Valid-Until "false";\nAcquire::Retries "5";\n' > /etc/apt/apt.conf.d/99archive

# Install R, sox and libsndfile/libfftw (required by seewave)
RUN apt-get update && \
    apt-get install -y --no-install-recommends opus-tools sox r-base r-cran-devtools libsndfile-dev libfftw3-3 libfftw3-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Install seewave (R package)
ARG SEEWAVE_VERSION=1.7.6
RUN if [ "$SEEWAVE_VERSION" = "latest" ]; then \
        Rscript -e 'install.packages("seewave")'; \
    else \
        Rscript -e "require(devtools); install.packages('https://cran.r-project.org/src/contrib/Archive/seewave/seewave_1.7.6.tar.gz', repos=NULL, type='source')"; \
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
