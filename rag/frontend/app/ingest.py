#!/usr/bin/env python3
import os
from typing import List, AsyncIterable
import asyncio
import functools
from db import get_db_connection, get_existing_sources
import boto3
import os
import tempfile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    CSVLoader,
    EverNoteLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredEPubLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredODTLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
)


# Load environment variables
bucket_name = os.environ.get("SOURCE_BUCKET", "documents")
chunk_size = 500
chunk_overlap = 50


# Map file extensions to document loaders and their arguments
LOADER_MAPPING = {
    ".csv": (CSVLoader, {}),
    ".doc": (UnstructuredWordDocumentLoader, {}),
    ".docx": (UnstructuredWordDocumentLoader, {}),
    ".enex": (EverNoteLoader, {}),
    ".epub": (UnstructuredEPubLoader, {}),
    ".html": (UnstructuredHTMLLoader, {}),
    ".md": (UnstructuredMarkdownLoader, {}),
    ".odt": (UnstructuredODTLoader, {}),
    ".pdf": (PyMuPDFLoader, {}),
    ".ppt": (UnstructuredPowerPointLoader, {}),
    ".pptx": (UnstructuredPowerPointLoader, {}),
    ".txt": (TextLoader, {"encoding": "utf8"}),
    # Add more mappings for other file extensions and loaders as needed
}

def get_file_list() -> List[str]:
    session = boto3.session.Session()
    client = session.client(service_name='s3')
    resp = client.list_objects_v2(Bucket=bucket_name)
    if resp is None or resp.get('Contents') is None:
        return []

    contents = resp.get('Contents')
    return [f.get('Key') for f in contents]

def download_files_to_dir(dir: str, files: List[str]):
    session = boto3.session.Session()
    client = session.client(service_name='s3')
    for f in files:
        full_path = os.path.join(dir, f)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        client.download_file(bucket_name, f, full_path)

def download_files_to_dir(dir: str, files: List[str]):
    session = boto3.session.Session()
    client = session.client(service_name='s3')
    for f in files:
        full_path = os.path.join(dir, f)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        client.download_file(bucket_name, f, full_path)

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
            if f in ignored_files:
                continue
            ext = "." + f.rsplit(".", 1)[-1]
            if ext not in LOADER_MAPPING:
                yield(f"Unsupported file extension '{ext}'\n")
                continue
            filtered_files.append(f)
        total_files = len(filtered_files)
        documents = []

        with tempfile.TemporaryDirectory() as temp_dir:
            download_future =  loop.run_in_executor(None, download_files_to_dir, temp_dir, filtered_files)
            while not download_future.done():
                yield(f"Still downloading files from {self.bucket_name}...\n")
                await asyncio.sleep(5)

            for i, file_path in enumerate(filtered_files):
                yield(f"Loading {file_path} ({i+1} / {total_files})\n")
                loader_class, loader_args = LOADER_MAPPING[ext]
                loader = loader_class(os.path.join(temp_dir, file_path), **loader_args)
                loader_future = loop.run_in_executor(None, loader.load)
                while not loader_future.done():
                    yield(f"Still loading {file_path}...\n")
                    await asyncio.sleep(3)
                load_result = loader_future.result()
                # fix paths
                for doc in load_result:
                    doc.metadata['source'] = file_path
                documents.extend(load_result)

        if len(documents) == 0:
            yield("Did not load any documents\n")
            return

        yield(f"Loaded {len(documents)} new documents from {self.bucket_name}\n")
        splitter_future = loop.run_in_executor(None, functools.partial(RecursiveCharacterTextSplitter, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
        while not splitter_future.done():
            yield("Still splitting documents...\n")
            await asyncio.sleep(3)
        text_splitter = splitter_future.result()
        texts_future = loop.run_in_executor(None, text_splitter.split_documents, documents)
        while not texts_future.done():
            yield("Still splitting documents...\n")
            await asyncio.sleep(3)
        texts = texts_future.result()
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
