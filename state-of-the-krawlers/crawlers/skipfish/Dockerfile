FROM python:3.9.16-slim

RUN apt update && apt install -y git make gcc libssl-dev libidn11-dev libz-dev libpcre3-dev \
    && pip install requests==2.28.2

WORKDIR /opt/skipfish

RUN git clone https://gitlab.com/kalilinux/packages/skipfish.git -b kali/2.10b-2kali7 --depth 1 . \
    && patch -d src < debian/patches/Fix-for-openssl-1.1.patch \
    && make

COPY auth_bootstrap.py .
RUN chmod +x auth_bootstrap.py

ENTRYPOINT ["./auth_bootstrap.py"]
