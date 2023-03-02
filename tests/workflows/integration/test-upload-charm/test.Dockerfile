FROM ubuntu:latest

RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections && \
    apt-get update \
        && apt-get --purge autoremove -y \
        && apt-get install -y apache2 \
            curl \
            git \
            libapache2-mod-php \
            libgmp-dev \
            php \
            php-curl \
            php-gd \
            php-gmp \
            php-mysql \
            php-symfony-yaml \
            php-xml \
            pwgen \
            python3 \
            python3-yaml \
            unzip
