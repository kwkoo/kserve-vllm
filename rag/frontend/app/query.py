#!/usr/bin/env python3
from langchain.chains import RetrievalQA
from langchain.chains.retrieval_qa.base import BaseRetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.vectorstores import Chroma
from langchain.llms import OpenAI

import os
from typing import AsyncIterable, Any
import requests
import asyncio
import logging


model = os.environ.get("MODEL", "/mnt/models")
openai_api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:8080/v1")
openai_api_key = os.environ.get("OPENAI_API_KEY", "EMPTY")
# For embeddings model, the example uses a sentence-transformers model
# https://www.sbert.net/docs/pretrained_models.html 
# "The all-mpnet-base-v2 model provides the best quality, while all-MiniLM-L6-v2 is 5 times faster and still offers good quality."
embeddings_model_name = os.environ.get("EMBEDDINGS_MODEL_NAME", "all-MiniLM-L6-v2")
persist_directory = os.environ.get("PERSIST_DIRECTORY", "db")
target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4))

retriever = None
llm = None

embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)


def initialize_query_engine():
    global retriever

    db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})

async def send_query_to_llm(qa: BaseRetrievalQA, prompt: str, output: dict[str, Any]):
    try:
        coro = qa.acall({'query': prompt})
        res = await coro
        if res.get('source_documents') is not None:
            output['source_documents'] = res['source_documents']
    except requests.exceptions.RequestException as err:
            output['error'] = err

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
            res = await qa.acall({'query': prompt})
            return res
        except Exception as e:
            raise e
        finally:
            callback.done

    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True)
    task = asyncio.create_task(send_llm_request())

    async for token in callback.aiter():
        yield token
    
    await task
    yield("\n==========\n")
    if task.exception() is not None:
        yield(f"exception: {task.exception()}\n")
    elif task.result() is not None and task.result().get("source_documents") is not None:
        yield('Sources\n')
        for doc in task.result().get('source_documents'):
            yield('----------\n')
            yield('→ ' + doc.metadata['source'] + ':\n')
            yield(doc.page_content)
            yield('\n\n')


initialize_query_engine()

async def main():
    async for token in llm_query('how do you install openshift'):
        print(token)

if __name__ == "__main__":
    asyncio.run(main())