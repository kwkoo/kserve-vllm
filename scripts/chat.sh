#!/bin/bash

# send to /v1/models to get list of loaded models
# GET /v1/models/{model}
# POST /v1/completions
# POST /v1/edits
# POST /v1/images/generations
# POST /v1/images/edits
# POST /v1/images/variations
# POST /v1/embeddings

curl localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"/mnt/models", "messages":[{"role":"system","content":"You are a helpful assistant."},{"role":"user","content":"Why is the sky blue?"}]}'
