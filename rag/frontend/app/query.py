#!/usr/bin/env python3
from langchain.chains import RetrievalQA
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain_openai import OpenAI

import logging
import sys
import json
import os
from typing import AsyncIterable, Any
import asyncio
from db import get_db_connection

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s [%(processName)s: %(process)d] [%(threadName)s: %(thread)d] [%(levelname)s] %(name)s: %(message)s")
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)


model = os.environ.get("MODEL", "/mnt/models")
reranker_model_name = os.environ.get("RERANKER_MODEL_NAME", "BAAI/bge-reranker-base")
openai_api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:8080/v1")
openai_api_key = os.environ.get("OPENAI_API_KEY", "EMPTY")
target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4))

retriever = None
llm = None


def parse_boolean_environent_variable(key: str, default=False) -> bool:
    env_var = os.getenv(key)
    if env_var is None:
        return default
    env_var = env_var.lower()
    val = default
    if env_var == '0' or env_var == 'false' or env_var == 'no' or env_var == 'n':
        val = False
    elif env_var == '1' or env_var == 'true' or env_var == 'yes' or env_var == 'y':
        val = True
    return val

def initialize_query_engine():
    global retriever

    db = get_db_connection()
    db_retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})
    retriever = db_retriever

    if parse_boolean_environent_variable('USE_RERANKER'):
        logger.info('using reranker')
        reranker_model = HuggingFaceCrossEncoder(model_name=reranker_model_name)
        compressor = CrossEncoderReranker(model=reranker_model, top_n=3)
        retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=db_retriever
        )
    else:
        logger.info('not using reranker')

async def llm_query(prompt: str) -> AsyncIterable[str]:
    callback = AsyncIteratorCallbackHandler()
    llm = OpenAI(
        model_name=model,
        openai_api_base=openai_api_base,
        openai_api_key=openai_api_key,
        callbacks=[callback],
        temperature=0,
        streaming=True
    )

    async def send_llm_request():
        try:
            res = await qa.ainvoke({'query': prompt})
            return res
        except Exception as e:
            raise e
        finally:
            callback.done

    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True)
    task = asyncio.create_task(send_llm_request())

    async for token in callback.aiter():
        yield json.dumps({'text': token}) + '\n'
    
    await task
    if task.exception() is not None:
        yield json.dumps({'error': task.exception()}) + '\n'
    elif task.result() is not None and task.result().get("source_documents") is not None:
        for doc in task.result().get('source_documents'):
            path = doc.metadata['source'] # should set this to doc.metadata['file_path']
            if doc.metadata.get('page') and doc.metadata.get('page') != -1:
                path = f"{path} - page {doc.metadata['page']}"
            obj = {
                'source': {
                    'path':path,
                    'contents':doc.page_content
                }
            }
            file_path = doc.metadata.get('file_path')
            if file_path is not None and (file_path.startswith('http://') or file_path.startswith('https://')):
                obj['source']['url'] = file_path
            yield json.dumps(obj) + '\n'


initialize_query_engine()

async def main():
    async for token in llm_query('describe the dip switch settings for the 2-axis servo amplifier'):
        print(token)

if __name__ == "__main__":
    asyncio.run(main())