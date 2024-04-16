PROJ=demo
IMAGE=ghcr.io/kwkoo/openai-rag
BUILDERNAME=multiarch-builder

BASE:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


# deploys all components to a single OpenShift cluster
.PHONY: deploy
deploy: ensure-logged-in turn-off-mtls
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


# once you turn mtls off, you will not be able to access the InferenceService
# from outside the cluster
.PHONY: turn-off-mtls
turn-off-mlts:
	@/bin/echo -n "waiting for ServiceMeshControlPlane..."
	@until oc get smcp/data-science-smcp -n istio-system >/dev/null 2>/dev/null; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	oc patch smcp/data-science-smcp \
	  --type json \
	  -p '[{"op":"replace","path":"/spec/security/dataPlane/mtls","value":false}]' \
	  -n istio-system

.PHONY: ensure-logged-in
ensure-logged-in:
	oc whoami
	@echo 'user is logged in'


.PHONY: image
image:
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
	  -t $(IMAGE) \
	  $(BASE)/frontend
	@#docker build \
	@#  --rm \
	@#  -t $(IMAGE) \
	@#  $(BASE)/frontend

# before running this, you need to port-forward to milvus and llm
# oc port-forward svc/milvus 19530:19530
# oc port-forward svc/llm-internal 8012:8012
.PHONY: remote
remote:
	docker run \
	  --name frontend \
	  --rm \
	  -it \
	  -p 8080:8080 \
	  -e DB_URL=http://host.docker.internal:19530 \
	  -e OPENAI_API_BASE=http://host.docker.internal:8012/v1 \
	  -v ./frontend/app/app.py:/app/app.py \
	  -v ./frontend/app/db.py:/app/db.py \
	  -v ./frontend/app/ingest.py:/app/ingest.py \
	  -v ./frontend/app/query.py:/app/query.py \
	  -v ./frontend/app/static:/app/static \
	  ghcr.io/kwkoo/openai-rag
