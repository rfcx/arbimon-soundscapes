FROM python:3.8-buster AS arbimon-soundscapes

# Buster is EOL; redirect apt to the Debian archive so apt-get update works.
RUN set -eux; \
    sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g; s|http://deb.debian.org/debian-security|http://archive.debian.org/debian-security|g; s|http://security.debian.org/debian-security|http://archive.debian.org/debian-security|g' /etc/apt/sources.list; \
    printf 'Acquire::Check-Valid-Until "false";\nAcquire::Retries "5";\n' > /etc/apt/apt.conf.d/99archive

# Install R, sox and libsndfile/libfftw (required by seewave).
# gfortran is REQUIRED: seewave -> tuneR -> signal, and the `signal` R package
# has Fortran sources (dpchim.f). Without gfortran its compile dies with
# `make: Error 127`, which silently leaves tuneR+seewave uninstalled.
RUN apt-get update && \
    apt-get install -y opus-tools sox r-base r-cran-devtools libsndfile-dev libfftw3-3 libfftw3-dev pkg-config gfortran

# Install seewave (R package)
ARG SEEWAVE_VERSION=1.7.6
# seewave needs the R packages fftw + tuneR (and tuneR needs signal); with
# repos=NULL (Archive tarball) R will NOT auto-resolve them, so install the
# deps from CRAN first. signal is listed explicitly so a missing toolchain
# surfaces here rather than as a confusing transitive tuneR failure.
RUN Rscript -e "install.packages(c('signal','fftw','tuneR'), repos='https://cloud.r-project.org')" && \
    if [ "$SEEWAVE_VERSION" = "latest" ]; then \
        Rscript -e 'install.packages("seewave", repos="https://cloud.r-project.org")'; \
    else \
        Rscript -e "install.packages(paste0('https://cran.r-project.org/src/contrib/Archive/seewave/seewave_', Sys.getenv('SEEWAVE_VERSION'), '.tar.gz'), repos=NULL, type='source')"; \
    fi && \
    Rscript -e "if (!requireNamespace('seewave', quietly=TRUE)) quit(status=1)"

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
