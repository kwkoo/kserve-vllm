FROM docker.io/kserve/vllmserver:latest

ENV HOME=/root

RUN \
  pip3 --no-cache-dir install fschat accelerate \
  && \
  chown -R :0 /root \
  && \
  chmod -R g=u /root
