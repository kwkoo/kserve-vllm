#!/usr/bin/env python3

import requests
import boto3
import os

models = {
    'phi': [
        'https://huggingface.co/microsoft/phi-2/raw/main/added_tokens.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/config.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/configuration_phi.py',
        'https://huggingface.co/microsoft/phi-2/raw/main/generation_config.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/merges.txt',
        'https://huggingface.co/microsoft/phi-2/resolve/main/model-00001-of-00002.safetensors',
        'https://huggingface.co/microsoft/phi-2/resolve/main/model-00002-of-00002.safetensors',
        'https://huggingface.co/microsoft/phi-2/raw/main/model.safetensors.index.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/modeling_phi.py',
        'https://huggingface.co/microsoft/phi-2/raw/main/special_tokens_map.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/tokenizer.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/tokenizer_config.json',
        'https://huggingface.co/microsoft/phi-2/raw/main/vocab.json'
    ],
    'mistral': [
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/raw/main/config.json',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/raw/main/generation_config.json',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main/pytorch_model-00001-of-00002.bin?download=true',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main/pytorch_model-00002-of-00002.bin?download=true',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/raw/main/pytorch_model.bin.index.json',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/raw/main/special_tokens_map.json',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/raw/main/tokenizer.json',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main/tokenizer.model?download=true',
        'https://huggingface.co/mistralai/Mistral-7B-v0.1/raw/main/tokenizer_config.json'
    ],
    'vicuna': [
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/raw/main/config.json',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/raw/main/generation_config.json',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/resolve/main/pytorch_model-00001-of-00002.bin?download=true',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/resolve/main/pytorch_model-00002-of-00002.bin?download=true',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/raw/main/pytorch_model.bin.index.json',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/raw/main/special_tokens_map.json',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/resolve/main/tokenizer.model?download=true',
        'https://huggingface.co/lmsys/vicuna-7b-v1.5/raw/main/tokenizer_config.json'
    ]
}


def filename_from_url(url: str) -> str:
    sep = url.rfind('?')
    if sep != -1:
        url = url[:sep]
    sep = url.rfind('/')
    if sep != -1:
        url = url[sep+1:]
    return url

def log(msg: str) -> None:
    print(msg, flush=True)

class Client:

    def __init__(self, access_key_id, access_secret, s3_endpoint):
        if access_key_id is None or access_key_id == '':
            raise Exception('access_key_id is not set')
        if access_secret is None or access_secret == '':
            raise Exception('access_secret is not set')
        if s3_endpoint is None or s3_endpoint == '':
            raise Exception('s3_endpoint is not set')
        session = boto3.session.Session()
        self.s3_client = session.client(
            service_name='s3',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=access_secret,
            endpoint_url=s3_endpoint
        )

    def upload_from_url_to_bucket(self, url: str, bucket: str, model_name: str) -> None:
        r = requests.get(url, stream=True)
        self.s3_client.upload_fileobj(r.raw, bucket, model_name + '/' + filename_from_url(url))

    def download_from_bucket(self, bucket: str) -> None:
        resp = self.s3_client.list_objects_v2(Bucket=bucket)
        if resp is None:
            log('could not get response')
            return
        contents = resp.get('Contents')
        if contents is None:
            log('bucket had no contents')
            return
        for entry in contents:
            key = entry.get('Key')
            if key is None:
                continue
            log(f'downloading {key}')
            self.s3_client.download_file(bucket, key, key)

    def upload_model_to_bucket(self, bucket, model_name, urls) -> None:
        if bucket is None or bucket == '':
            raise Exception('bucket is not set')
        for url in urls:
            log(f'uploading {url}')
            self.upload_from_url_to_bucket(url, bucket, model_name)

#download_from_bucket(bucket)

if __name__ == '__main__':
    client = Client(
        os.environ.get('AWS_ACCESS_KEY_ID'),
        os.environ.get('AWS_SECRET_ACCESS_KEY'),
        os.environ.get('AWS_ENDPOINT_URL_S3')
    )
    model_name = os.environ.get('MODEL')
    if model_name is None:
        raise Exception('MODEL environment variable is not set')
    model_urls = models.get(model_name)
    if model_urls is None:
        raise Exception(f'could not get URLs for {model_name}')
    client.upload_model_to_bucket(os.environ.get('S3_BUCKET', 'models'), model_name, model_urls)
