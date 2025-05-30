PROJ=demo
IMAGE=ghcr.io/kwkoo/openai-rag
IPEX_IMAGE=ghcr.io/kwkoo/openai-rag-ipex
BUILDERNAME=multiarch-builder

BASE:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


# deploys all components to a single OpenShift cluster
.PHONY: deploy
deploy: ensure-logged-in
	oc new-project $(PROJ); \
	if [ $$? -eq 0 ]; then sleep 3; fi
	oc get limitrange -n $(PROJ) >/dev/null 2>/dev/null \
	&& \
	if [ $$? -eq 0 ]; then \
	  oc get limitrange -n $(PROJ) -o name | xargs oc delete -n $(PROJ); \
	fi

	oc apply -n $(PROJ) -k $(BASE)/yaml/base/milvus/
	oc apply -n $(PROJ) -k $(BASE)/yaml/base/frontend/

	@/bin/echo -n 'waiting for route to show up...'
	@until oc get -n $(PROJ) route/frontend >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo "done"
	@echo "access the frontend at http://`oc get -n $(PROJ) route/frontend -o jsonpath='{.spec.host}'`"


.PHONY: clean
clean:
	oc delete -n $(PROJ) -k $(BASE)/yaml/base/frontend/ 2>/dev/null || exit 0
	oc delete -n $(PROJ) -k $(BASE)/yaml/base/milvus/ 2>/dev/null || exit 0
	oc delete -n $(PROJ) pvc -l app=milvus 2>/dev/null || exit 0


.PHONY: ensure-logged-in
ensure-logged-in:
	oc whoami
	@echo 'user is logged in'


.PHONY: image
image:
	docker buildx use $(BUILDERNAME) || docker buildx create --name $(BUILDERNAME)
	docker buildx build \
	  --push \
	  --provenance false \
	  --sbom false \
	  --platform=linux/amd64 \
	  --rm \
	  -t $(IMAGE):amd64 \
	  -f $(BASE)/frontend/Dockerfile.amd64 \
	  $(BASE)/frontend
	docker buildx build \
	  --push \
	  --provenance false \
	  --sbom false \
	  --platform=linux/arm64 \
	  --rm \
	  -t $(IMAGE):arm64 \
	  -f $(BASE)/frontend/Dockerfile.arm64 \
	  $(BASE)/frontend
	docker pull $(IMAGE):amd64
	docker pull $(IMAGE):arm64
	docker manifest create \
	  $(IMAGE):latest \
	  --amend $(IMAGE):amd64 \
	  --amend $(IMAGE):arm64
	docker manifest push $(IMAGE):latest


.PHONY: arm
arm:
	docker build -t ghcr.io/kwkoo/armfrontend -f $(BASE)/frontend/Dockerfile.arm $(BASE)/frontend


.PHONY: ipex-image
ipex-image:
	-mkdir -p $(BASE)/docker-cache 2>/dev/null
	docker buildx use $(BUILDERNAME) || docker buildx create --name $(BUILDERNAME) --use --buildkitd-flags '--oci-worker-gc-keepstorage 50000'
	docker buildx build \
	  --push \
	  --provenance false \
	  --sbom false \
	  --platform=linux/amd64 \
	  --cache-to type=local,dest=$(BASE)/docker-cache,mode=max \
	  --cache-from type=local,src=$(BASE)/docker-cache \
	  --rm \
	  -f $(BASE)/frontend/Dockerfile.ipex \
	  -t $(IPEX_IMAGE) \
	  $(BASE)/frontend


# before running this, you need to port-forward to milvus and llm
# oc port-forward svc/milvus 19530:19530
# oc port-forward svc/llm-internal 8012:8012
# oc port-forward svc/minio 9000:9000
.PHONY: remote
remote:
	docker run \
	  --name frontend \
	  --rm \
	  -it \
	  -p 8080:8080 \
	  -e DB_URL=http://host.docker.internal:19530 \
	  -e OPENAI_API_BASE=http://host.docker.internal:8012/v1 \
	  -e AWS_ACCESS_KEY_ID=minio \
	  -e AWS_SECRET_ACCESS_KEY=minio123 \
	  -e AWS_ENDPOINT_URL_S3=http://host.docker.internal:9000 \
	  -v ./frontend/app/app.py:/app/app.py \
	  -v ./frontend/app/db.py:/app/db.py \
	  -v ./frontend/app/ingest.py:/app/ingest.py \
	  -v ./frontend/app/query.py:/app/query.py \
	  -v ./frontend/app/static:/app/static \
	  ghcr.io/kwkoo/openai-rag


# before running this, you need to port-forward to milvus and llm
# oc port-forward svc/milvus 19530:19530
# oc port-forward svc/llm-internal 8012:8012
# oc port-forward svc/minio 9000:9000
.PHONY: debug
debug:
	docker run \
	  --name frontend \
	  --rm \
	  -it \
	  -p 8080:8080 \
	  -e DB_URL=http://host.docker.internal:19530 \
	  -e OPENAI_API_BASE=http://host.docker.internal:8012/v1 \
	  -e AWS_ACCESS_KEY_ID=minio \
	  -e AWS_SECRET_ACCESS_KEY=minio123 \
	  -e AWS_ENDPOINT_URL_S3=http://host.docker.internal:9000 \
	  -v ./frontend/app/app.py:/app/app.py \
	  -v ./frontend/app/db.py:/app/db.py \
	  -v ./frontend/app/ingest.py:/app/ingest.py \
	  -v ./frontend/app/query.py:/app/query.py \
	  -v ./frontend/app/static:/app/static \
	  ghcr.io/kwkoo/openai-rag \
	  tail -f /dev/null
