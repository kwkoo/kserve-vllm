#!/usr/bin/env python3
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.callbacks.streaming_stdout import BaseCallbackHandler
from langchain.vectorstores import Chroma
from langchain.llms import OpenAI

import os
import threading
import queue
from typing import Any, Generator
import requests

# Copied from https://github.com/langchain-ai/langchain/issues/4950#issuecomment-1790074587
class QueueCallbackHandler(BaseCallbackHandler):
    def __init__(self, queue):
        self.queue = queue

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.queue.put(token)

    def on_llm_end(self, *args, **kwargs) -> Any:
        return self.queue.empty()

def stream(cb: Any, llm_queue: queue.Queue) -> Generator:
    job_done = object()

    def task(res):
        cb(res)
        llm_queue.put(job_done)

    res = dict()
    t = threading.Thread(target=task, args=(res,))
    t.start()

    while True:
        try:
            item = llm_queue.get(True, timeout=5)
            if item is job_done:
                break
            yield(item)
        except queue.Empty:
            continue

    t.join()
    yield('\n==========\n')
    if res is None:
        yield('could not get results from LLM\n')
        return
    if res.get('error') is not None:
        yield('error: ' + str(res.get('error')) + '\n')
    if res.get('source_documents') is not None:
        yield('Sources\n')
        for doc in res['source_documents']:
            yield('----------\n')
            yield('→ ' + doc.metadata['source'] + ':\n')
            yield(doc.page_content)
            yield('\n\n')


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

def llm_query(prompt: str):
    output_queue = queue.Queue()
    llm = OpenAI(
        model_name=model,
        openai_api_base=openai_api_base,
        openai_api_key=openai_api_key,
        callbacks=[QueueCallbackHandler(output_queue)],
        temperature=0,
        streaming=True
    )
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True)

    def cb(output):
        try:
            res = qa(prompt)
            if res.get('source_documents') is not None:
                output['source_documents'] = res['source_documents']
        except requests.exceptions.RequestException as err:
            output['error'] = err
            return

    yield from stream(cb, output_queue)


initialize_query_engine()

#if __name__ == "__main__":
#    main()