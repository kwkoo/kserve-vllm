#!/usr/bin/env python3
import os
import glob
from typing import List
import threading
import time

from langchain.document_loaders import (
    CSVLoader,
    EverNoteLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredEmailLoader,
    UnstructuredEPubLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredODTLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
)

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document


# Load environment variables
persist_directory = os.environ.get('PERSIST_DIRECTORY', 'db')
source_directory = os.environ.get('SOURCE_DIRECTORY', 'source_documents')
embeddings_model_name = os.environ.get('EMBEDDINGS_MODEL_NAME', 'all-MiniLM-L6-v2')
chunk_size = 500
chunk_overlap = 50

# Custom document loaders
class MyElmLoader(UnstructuredEmailLoader):
    """Wrapper to fallback to text/plain when default does not work"""

    def load(self) -> List[Document]:
        """Wrapper adding fallback for elm without html"""
        try:
            try:
                doc = UnstructuredEmailLoader.load(self)
            except ValueError as e:
                if 'text/html content not found in email' in str(e):
                    # Try plain text
                    self.unstructured_kwargs["content_source"]="text/plain"
                    doc = UnstructuredEmailLoader.load(self)
                else:
                    raise
        except Exception as e:
            # Add file_path to exception message
            raise type(e)(f"{self.file_path}: {e}") from e

        return doc


# Map file extensions to document loaders and their arguments
LOADER_MAPPING = {
    ".csv": (CSVLoader, {}),
    # ".docx": (Docx2txtLoader, {}),
    ".doc": (UnstructuredWordDocumentLoader, {}),
    ".docx": (UnstructuredWordDocumentLoader, {}),
    ".enex": (EverNoteLoader, {}),
    ".eml": (MyElmLoader, {}),
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

    def load_documents_and_split(self, ignored_files: List[str] = []):
        """
        Loads all documents from the source documents directory, ignoring specified files
        """
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
            documents.extend(loader.load())

        if len(documents) == 0:
            yield("Did not load any documents\n")
            return

        yield(f"Loaded {len(documents)} new documents from {source_directory}\n")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        texts = text_splitter.split_documents(documents)
        yield(f"Split into {len(texts)} chunks of text (max. {chunk_size} tokens each)\n")
        self.texts = texts

def does_vectorstore_exist(persist_directory: str) -> bool:
    """
    Checks if vectorstore exists
    """
    if os.path.exists(os.path.join(persist_directory, 'chroma.sqlite3')):
        return True
    
    return False

def create_embeddings(db, embeddings, texts):
    if db is None: # db does not exist
        db = Chroma.from_documents(texts, embeddings, persist_directory=persist_directory)
    else: # db exists
        db.add_documents(texts)

    db.persist()
    time.sleep(10)

def ingest_documents():
    # Create embeddings
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)

    ingester = Ingester(source_directory)

    db = None
    ignored_files = []
    if does_vectorstore_exist(persist_directory):
        db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        collection = db.get()
        ignored_files = [metadata['source'] for metadata in collection['metadatas']]
    yield from ingester.load_documents_and_split(ignored_files)
    if ingester.texts is None:
        return
    yield(f"Creating embeddings in vector database, may a few minutes...\n")
    embeddings_thread = threading.Thread(
        target=create_embeddings,
        args=(db, embeddings, ingester.texts)
    )
    embeddings_thread.start()
    while embeddings_thread.is_alive():
        yield("embeddings thread still running...\n")
        time.sleep(3)
    embeddings_thread.join()
    yield(f"Ingestion complete\n")

#def main():
#    for s in handler():
#        print(s)
#
#if __name__ == "__main__":
#    main()
