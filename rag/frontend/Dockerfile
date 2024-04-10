FROM nvcr.io/nvidia/cuda:12.3.1-devel-ubi9 AS base-amd64

RUN \
  yum update -y \
  && \
  yum install -y python3-pip python3-devel \
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
RUN \
  --mount=type=bind,source=./app/requirements.txt,target=/app/requirements.txt \
  pip3 install --upgrade pip \
  && \
  pip3 install --no-cache-dir -r requirements.txt


FROM docker.io/python:3.11 AS base-arm64

WORKDIR /app
RUN \
  --mount=type=bind,source=./app/requirements.txt,target=/app/requirements.txt \
  pip3 install --upgrade pip \
  && \
  UNAME_M=arm64 UNAME_p=arm LLAMA_NO_METAL=1 pip3 install --no-cache-dir -r requirements.txt


ARG TARGETARCH
FROM base-$TARGETARCH

ARG EMBEDDINGS_MODEL="all-MiniLM-L6-v2"
ENV HOME=/root
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
EXPOSE 8080

RUN \
  python3 -c "from langchain.embeddings import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='$EMBEDDINGS_MODEL')" \
  && \
  python3 -c "import nltk; nltk.download('punkt')" \
  && \
  chown -R :0 /root /app \
  && \
  chmod 775 /root \
  && \
  chmod -R g=u /app /root

COPY --chown=:0 ./app/ /app/
