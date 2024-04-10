#!/usr/bin/env python3
import os
from typing import List, AsyncIterable
import asyncio
import functools
from db import get_db_connection, get_existing_sources
from langchain.document_loaders import S3FileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import boto3


# Load environment variables
bucket_name = os.environ.get("SOURCE_BUCKET", "documents")
chunk_size = 500
chunk_overlap = 50

supported_extensions = ['.csv', '.doc', '.docx', '.epub', '.html', '.md', '.odt', '.pdf', '.ppt', '.pptx', '.txt']

def get_file_list() -> List[str]:
    session = boto3.session.Session()
    client = session.client(service_name='s3')
    resp = client.list_objects_v2(Bucket=bucket_name)
    if resp is None or resp.get('Contents') is None:
        return []

    contents = resp.get('Contents')
    return [f.get('Key') for f in contents]

class Ingester:
    texts = None

    def __init__(self, bucket_name) -> None:
        self.bucket_name = bucket_name

    async def load_documents_and_split(self, ignored_files: List[str] = []) -> AsyncIterable[str]:
        """
        Loads all documents from the source documents directory, ignoring specified files
        """
        loop = asyncio.get_event_loop()
        yield(f"Loading documents from {self.bucket_name}\n")
        filtered_files = []
        for f in get_file_list():
            if f"s3://{self.bucket_name}/{f}" not in ignored_files:
                filtered_files.append(f)
        total_files = len(filtered_files)
        documents = []
        for i, file_path in enumerate(filtered_files):
            ext = "." + file_path.rsplit(".", 1)[-1]
            if ext not in supported_extensions:
                yield(f"Unsupported file extension '{ext}'\n")
                continue
            yield(f"Loading {file_path} ({i+1} / {total_files})\n")
            loader = S3FileLoader(self.bucket_name, file_path)
            load_result = await loop.run_in_executor(None, loader.load)
            documents.extend(load_result)

        if len(documents) == 0:
            yield("Did not load any documents\n")
            return

        yield(f"Loaded {len(documents)} new documents from {self.bucket_name}\n")
        text_splitter = await loop.run_in_executor(None, functools.partial(RecursiveCharacterTextSplitter, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
        texts = await loop.run_in_executor(None, text_splitter.split_documents, documents)
        yield(f"Split into {len(texts)} chunks of text (max. {chunk_size} tokens each)\n")
        self.texts = texts

async def ingest_documents() -> AsyncIterable[str]:
    ingester = Ingester(bucket_name)

    ignored_files = get_existing_sources()
    if len(ignored_files) > 0:
        yield(f"ignoring {ignored_files}\n")
    db = get_db_connection()

    async for line in ingester.load_documents_and_split(ignored_files):
        yield line
    if ingester.texts is None:
        return

    yield(f"Creating embeddings in vector database, may a few minutes...\n")

    loop = asyncio.get_event_loop()
    embeddings_future = loop.run_in_executor(None, db.add_documents, ingester.texts)
    while not embeddings_future.done():
        yield("embeddings thread still running...\n")
        await asyncio.sleep(5)

    yield(f"Ingestion complete\n")


async def main():
    async for token in ingest_documents():
        print(token)

if __name__ == "__main__":
    asyncio.run(main())
