FROM nvcr.io/nvidia/cuda:12.3.1-devel-ubi9 AS base-amd64

ARG TARGETARCH
RUN \
  --mount=type=cache,target=/var/cache/rag-base-$TARGETARCH \
  yum update -y \
  && \
  yum install -y python3-pip python3-devel sqlite-devel \
  && \
  yum clean all

ENV \
  LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/lib/python3.9/site-packages/nvidia/cudnn/lib \
  CUDA_DIR=/usr/local/cuda \
  CUDA_PATH=/usr/local/cuda \
  CUDA_INSTALL_DIR=/usr/local/cuda \
  CUDA_HOME=/usr/local/cuda \
  NVIDIA_VISIBLE_DEVICES=all

WORKDIR /app
COPY --chown=:0 ./app/requirements.txt /app/
ARG TARGETARCH
RUN \
  --mount=type=cache,target=/var/cache/rag-pip-$TARGETARCH \
  pip3 install --no-cache-dir -r requirements.txt \
  && \
  pip3 install --no-cache-dir pysqlite3-binary


FROM docker.io/python:3.11 AS base-arm64

WORKDIR /app
COPY --chown=:0 ./app/requirements.txt /app/
ARG TARGETARCH
RUN \
  --mount=type=cache,target=/var/cache/rag-pip-$TARGETARCH \
  UNAME_M=arm64 UNAME_p=arm LLAMA_NO_METAL=1 pip3 install --no-cache-dir -r requirements.txt


ARG TARGETARCH
FROM base-$TARGETARCH

ARG EMBEDDINGS_MODEL="all-MiniLM-L6-v2"
ENV HOME=/root
CMD ["python3", "./app.py"]
EXPOSE 8080

RUN \
  --mount=type=cache,target=/var/cache/rag-$TARGETARCH \
  python3 -c "from langchain.embeddings import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='$EMBEDDINGS_MODEL')" \
  && \
  python3 -m nltk.downloader all \
  && \
  chown -R :0 /root /app \
  && \
  chmod 775 /root \
  && \
  chmod -R g=u /app /root

COPY --chown=:0 ./app/ /app/
