#!/bin/bash

# send to /v1/models to get list of loaded models
# GET /v1/models/{model}
# POST /v1/completions
# POST /v1/edits
# POST /v1/images/generations
# POST /v1/images/edits
# POST /v1/images/variations
# POST /v1/embeddings

llm_url="$(oc get inferenceservice/llm -n demo -o jsonpath='{.status.url}')"

if [ -z "$llm_url" ]; then
  echo "could not retrieve LLM URL"
  exit 1
fi

curl ${llm_url}/v1/chat/completions \
  -k \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"model":"/mnt/models", "temperature":0, "messages":[{"role":"user","content":"Hello"}]}'

