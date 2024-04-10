#!/usr/bin/env python3
import os
import glob
from typing import List, AsyncIterable
import asyncio
import functools
from db import get_db_connection, get_existing_sources

from langchain.document_loaders import (
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

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings


# Load environment variables
source_directory = os.environ.get('SOURCE_DIRECTORY', 'source_documents')
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

class Ingester:
    texts = None

    def __init__(self, source_directory) -> None:
        self.source_directory = source_directory

    async def load_documents_and_split(self, ignored_files: List[str] = []) -> AsyncIterable[str]:
        """
        Loads all documents from the source documents directory, ignoring specified files
        """
        loop = asyncio.get_event_loop()
        yield(f"Loading documents from {self.source_directory}\n")
        all_files = []
        for ext in LOADER_MAPPING:
            all_files.extend(
                glob.glob(os.path.join(self.source_directory, f"**/*{ext}"), recursive=True)
            )
        filtered_files = [file_path for file_path in all_files if file_path not in ignored_files]
        total_files = len(filtered_files)
        documents = []
        for i, file_path in enumerate(filtered_files):
            ext = "." + file_path.rsplit(".", 1)[-1]
            if ext not in LOADER_MAPPING:
                yield(f"Unsupported file extension '{ext}'\n")
                continue
            yield(f"Loading {file_path} ({i+1} / {total_files})\n")
            loader_class, loader_args = LOADER_MAPPING[ext]
            loader = loader_class(file_path, **loader_args)
            load_result = await loop.run_in_executor(None, loader.load)
            documents.extend(load_result)

        if len(documents) == 0:
            yield("Did not load any documents\n")
            return

        yield(f"Loaded {len(documents)} new documents from {source_directory}\n")
        text_splitter = await loop.run_in_executor(None, functools.partial(RecursiveCharacterTextSplitter, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
        texts = await loop.run_in_executor(None, text_splitter.split_documents, documents)
        yield(f"Split into {len(texts)} chunks of text (max. {chunk_size} tokens each)\n")
        self.texts = texts

async def ingest_documents() -> AsyncIterable[str]:
    ingester = Ingester(source_directory)

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
