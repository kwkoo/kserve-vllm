# Workaround for the older version of sqlite3 in the nvidia CUDA image
# https://docs.trychroma.com/troubleshooting#sqlite
import sys
import importlib.util
if importlib.util.find_spec('pysqlite3') is not None:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import logging
import os

from flask import Flask, redirect, Response, request, abort
from ingest import ingest_documents
from query import llm_query, initialize_query_engine
from delete_directory import delete_database

# do not log access to health probes
class LogFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "/livez" in msg or "/readyz" in msg: return False
        return True
logging.getLogger("werkzeug").addFilter(LogFilter())

app = Flask(__name__, static_url_path='')

@app.route("/")
def home():
    return redirect("/index.html")

@app.route("/livez")
@app.route("/readyz")
@app.route("/healthz")
def health():
    return "OK"

@app.route("/api/ingest")
def ingest():
    return Response(ingest_documents(), mimetype='text/plain')

@app.route("/api/query", methods=['POST', 'PUT'])
def query():
    data = request.get_json()
    if data is None:
        abort(500, description='JSON not found in request body')
    if data['prompt'] is None:
        abort(500, description='JSON in request body does not contain prompt')
    return Response(llm_query(data['prompt']), mimetype='text/plain')

@app.route("/api/deletedb")
def deletedb():
    try:
        delete_database()
        return "OK"
    except:
        abort(500, description='could not delete database')

@app.route("/api/refreshdb")
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