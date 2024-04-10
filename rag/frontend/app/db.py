import os
import pymilvus
from typing import List
from langchain.vectorstores import Milvus
from langchain.embeddings import HuggingFaceEmbeddings

db_url = os.environ.get('DB_URL', 'http://127.0.0.1:19530')

# For embeddings model, the example uses a sentence-transformers model
# https://www.sbert.net/docs/pretrained_models.html 
# "The all-mpnet-base-v2 model provides the best quality, while all-MiniLM-L6-v2 is 5 times faster and still offers good quality."
embeddings_model_name = os.environ.get("EMBEDDINGS_MODEL_NAME", "all-MiniLM-L6-v2")

collection_name = 'LangChainCollection'

embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)

def get_db_connection() -> Milvus:
    address = db_url
    if address.startswith('http://'):
        address = address[len('http://'):]
    elif address.startswith('https://'):
        address = address[len('https://'):]
    return Milvus(connection_args={'address': address}, embedding_function=embeddings)

def delete_database():
    client = pymilvus.MilvusClient(uri=db_url)
    client.drop_collection(collection_name)

def get_existing_sources() -> List[str]:
    pymilvus.connections.connect(uri=db_url)
    try:
        collection = pymilvus.Collection(collection_name)
    except pymilvus.exceptions.SchemaNotReadyException:
        return []
    collection.load()
    sources = []
    query_iterator = collection.query_iterator(100, 65536, '', ['source'])
    while True:
        docs = query_iterator.next()
        if len(docs) == 0:
            break
        for doc in docs:
            source = doc.get("source")
            if source not in sources:
                sources.append(source)
    return sources