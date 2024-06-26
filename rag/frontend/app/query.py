#!/usr/bin/env python3
from langchain.chains import RetrievalQA
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain_openai import OpenAI

import json
import os
from typing import AsyncIterable, Any
import asyncio
from db import get_db_connection


model = os.environ.get("MODEL", "/mnt/models")
openai_api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:8080/v1")
openai_api_key = os.environ.get("OPENAI_API_KEY", "EMPTY")
target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4))

retriever = None
llm = None



def initialize_query_engine():
    global retriever

    db = get_db_connection()
    retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})

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
            if doc.metadata.get('page') and doc.metadata.get('page') != 0:
                path = f"{path} - page {doc.metadata['page']}"
            yield json.dumps({'source':{'path':path, 'contents':doc.page_content}}) + '\n'


initialize_query_engine()

async def main():
    async for token in llm_query('how do you install openshift'):
        print(token)

if __name__ == "__main__":
    asyncio.run(main())