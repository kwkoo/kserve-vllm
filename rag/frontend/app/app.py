# Workaround for the older version of sqlite3 in the nvidia CUDA image
# https://docs.trychroma.com/troubleshooting#sqlite
import sys
import importlib.util
if importlib.util.find_spec('pysqlite3') is not None:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, RedirectResponse

from ingest import ingest_documents
from query import llm_query, initialize_query_engine
from delete_directory import delete_database


# do not log access to health probes
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/healthz") == -1 and record.getMessage().find("/livez") == -1 and record.getMessage().find("/readyz") == -1

# Filter out health probes
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
@app.get("/index.html")
def home():
    return RedirectResponse("/static/index.html")

@app.get("/livez")
@app.get("/readyz")
@app.get("/healthz")
def health():
    return "OK"


@app.get("/api/ingest")
async def ingest():
    return StreamingResponse(ingest_documents(), media_type='text/plain')


class Prompt(BaseModel):
    prompt: str

@app.post("/api/query")
@app.put("/api/query")
async def query(body: Prompt):
    if body.prompt == '':
        return {'error': 'JSON in request body does not contain prompt'}
    return StreamingResponse(llm_query(body.prompt), media_type="text/plain")


# @app.route("/api/deletedb")
@app.get("/api/deletedb")
def deletedb():
    try:
        delete_database()
        return "OK"
    except:
        raise HTTPException(status_code=500, detail='could not delete database')


@app.get("/api/refreshdb")
def refreshdb():
    initialize_query_engine()
    return "OK"


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    port_str = os.getenv('PORT', '8080')
    port = 0
    try:
        port = int(port_str)
    except ValueError:
        logging.error(f'could not convert PORT ({port_str}) to integer')
        sys.exit(1)

    app.run(host='0.0.0.0', port=port)