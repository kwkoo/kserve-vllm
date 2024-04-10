PROJ=demo
IMAGE=ghcr.io/kwkoo/openai-rag
BUILDERNAME=multiarch-builder

BASE:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

.PHONY: deploy clean ensure-logged-in image

# deploys all components to a single OpenShift cluster
deploy: ensure-logged-in
	oc new-project $(PROJ); \
	if [ $$? -eq 0 ]; then sleep 3; fi
	oc get limitrange -n $(PROJ) >/dev/null 2>/dev/null \
	&& \
	if [ $$? -eq 0 ]; then \
	  oc get limitrange -n $(PROJ) -o name | xargs oc delete -n $(PROJ); \
	fi

	oc apply -n $(PROJ) -k $(BASE)/yaml/base/milvus/

	SUFFIX=`oc whoami --show-console | sed 's/^[^.]*//'`; \
	oc kustomize $(BASE)/yaml/base/frontend/ \
	| \
	sed \
	  -e "s/frontend-.*/frontend-$(PROJ)$$SUFFIX/g" \
	| \
	oc apply -n $(PROJ) -f -; \
	oc kustomize $(BASE)/yaml/base/routes/ \
	| \
	sed \
	  -e "s/frontend-.*/frontend-$(PROJ)$$SUFFIX/g" \
	| \
	oc apply -f -

	@/bin/echo -n 'waiting for routes to show up...'
	@until oc get -n istio-system route/frontend >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo "done"
	@echo "access the frontend at http://`oc get -n istio-system route/frontend -o jsonpath='{.spec.host}'`"

clean:
	oc delete -n $(PROJ) -k $(BASE)/yaml/base/frontend/ 2>/dev/null || exit 0
	oc delete -k $(BASE)/yaml/base/routes/ 2>/dev/null || exit 0
	oc delete -n $(PROJ) -k $(BASE)/yaml/base/milvus/ 2>/dev/null || exit 0
	oc delete -n $(PROJ) pvc -l app=milvus 2>/dev/null || exit 0


ensure-logged-in:
	oc whoami
	@echo 'user is logged in'


image:
	-mkdir -p $(BASE)/docker-cache/amd64 $(BASE)/docker-cache/arm64 2>/dev/null
	docker buildx use $(BUILDERNAME) || docker buildx create --name $(BUILDERNAME) --use
	docker buildx build \
	  --push \
	  --provenance false \
	  --sbom false \
	  --platform=linux/amd64 \
	  --cache-to type=local,dest=$(BASE)/docker-cache/amd64,mode=max \
	  --cache-from type=local,src=$(BASE)/docker-cache/amd64 \
	  --rm \
	  -t $(IMAGE):amd64 \
	  $(BASE)/frontend
	docker buildx build \
	  --push \
	  --provenance false \
	  --sbom false \
	  --platform=linux/arm64 \
	  --cache-to type=local,dest=$(BASE)/docker-cache/arm64,mode=max \
	  --cache-from type=local,src=$(BASE)/docker-cache/arm64 \
	  --rm \
	  -t $(IMAGE):arm64 \
	  $(BASE)/frontend
	docker manifest create \
	  $(IMAGE):latest \
	  --amend $(IMAGE):amd64 \
	  --amend $(IMAGE):arm64
	docker manifest push --purge $(IMAGE):latest
	@#docker build \
	@#  --rm \
	@#  -t $(IMAGE) \
	@#  $(BASE)/frontend
