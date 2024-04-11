FROM nvcr.io/nvidia/cuda:12.4.1-devel-ubuntu22.04 AS builder

RUN \
  --mount=type=bind,source=./app/requirements.txt,target=/app/requirements.txt \
  apt update -y \
  && \
  apt install -y curl \
  && \
  apt clean -y \
  && \
  curl \
      -Lo /tmp/miniconda.sh \
      https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
  && \
  bash /tmp/miniconda.sh -b -p /usr/local/miniconda \
  && \
  rm -f /tmp/miniconda.sh \
  && \
  . /usr/local/miniconda/etc/profile.d/conda.sh \
  && \
  conda create --name app python=3.11 -y \
  && \
  conda activate app \
  && \
  chown -R :0 /usr/local/miniconda \
  && \
  chmod 775 /usr/local/miniconda \
  && \
  chmod -R g=u /usr/local/miniconda \
  && \
  pip install --no-cache -r /app/requirements.txt

FROM nvcr.io/nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV \
  LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/miniconda/envs/app/lib/python3.11/site-packages/nvidia/cudnn/lib \
  CUDA_DIR=/usr/local/cuda \
  CUDA_PATH=/usr/local/cuda \
  CUDA_INSTALL_DIR=/usr/local/cuda \
  CUDA_HOME=/usr/local/cuda \
  NVIDIA_VISIBLE_DEVICES=all \
  HOME=/root

COPY --from=builder --chown=:0 /usr/local/miniconda /usr/local/miniconda

ARG EMBEDDINGS_MODEL="all-MiniLM-L6-v2"
RUN \
  apt update -y \
  && \
  apt install -y libgl1-mesa-glx libglib2.0-0 poppler-utils libtesseract-dev tesseract-ocr \
  && \
  apt clean -y \
  && \
  echo 'set -o vi' >> $HOME/.bashrc \
  && \
  echo '. /usr/local/miniconda/etc/profile.d/conda.sh' >> $HOME/.bashrc \
  && \
  echo 'conda activate app' >> $HOME/.bashrc \
  && \
  . /usr/local/miniconda/etc/profile.d/conda.sh \
  && \
  conda activate app \
  && \
  python3 -c "from langchain.embeddings import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='$EMBEDDINGS_MODEL')" \
  && \
  python3 -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')" \
  && \
  python -c 'from transformers import TableTransformerModel; TableTransformerModel.from_pretrained("microsoft/table-transformer-structure-recognition")' \
  && \
  python -c 'import timm; timm.create_model("resnet18.a1_in1k", pretrained=True)' \
  && \
  python -c 'from unstructured_inference.models.base import get_model; get_model("yolox")' \
  && \
  chmod -R g=u /root

WORKDIR /app
CMD ["bash", "-c", ". /usr/local/miniconda/etc/profile.d/conda.sh; conda activate app; uvicorn app:app --host 0.0.0.0 --port 8080"]
EXPOSE 8080

COPY --chown=:0 ./app/ /app/
RUN \
  chmod 775 /app \
  && \
  chmod -R g=u /app
