# RAG Demo

The code was copied from [`PromptEngineer48 / Ollama`](https://github.com/PromptEngineer48/Ollama)

This demo runs against an LLM that is running on KServe and vLLM.

## Deploying on OpenShift

It is assumed that you have installed OpenShift AI and you have deployed an `InferenceService` named `llm`.

01. To deploy the RAG demo,

		make deploy

	When the application has been deployed, it should output the URLs of the file browser and the frontend

01. Access the file browser and upload the documents you want to index

01. Access the frontend and click on the link to ingest documents to the vector database

01. After the document ingestion process has completed, click on the `Refresh Database` button - this forces the query engine to refresh its connection to the vector database

01. Access the front page of the frontend again and click on the link to run your queries

01. Type your query into the prompt text field and click the `Query` button


## Resources

*   Download embeddings

		EMBEDDINGS_MODEL="all-MiniLM-L6-v2"

		python3 -c "from langchain.embeddings import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='$EMBEDDINGS_MODEL')"

*   Download NLTK resources

		python3 -m nltk.downloader all

*   [Langchain Milvus](https://python.langchain.com/docs/integrations/vectorstores/milvus/)

*   [Running Milvus in docker](https://raw.githubusercontent.com/milvus-io/milvus/master/scripts/standalone_embed.sh)
