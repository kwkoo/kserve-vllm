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

	SUFFIX=`oc whoami --show-console | sed 's/^[^.]*//'`; \
	oc kustomize $(BASE)/yaml/base/frontend/ \
	| \
	sed \
	  -e "s/frontend-.*/frontend-$(PROJ)$$SUFFIX/g" \
	  -e "s/filebrowser-.*/filebrowser-$(PROJ)$$SUFFIX/g" \
	| \
	oc apply -n $(PROJ) -f -; \
	oc kustomize $(BASE)/yaml/base/routes/ \
	| \
	sed \
	  -e "s/frontend-.*/frontend-$(PROJ)$$SUFFIX/g" \
	  -e "s/filebrowser-.*/filebrowser-$(PROJ)$$SUFFIX/g" \
	| \
	oc apply -f -

	@/bin/echo -n 'waiting for routes to show up...'
	@until oc get -n istio-system route/frontend >/dev/null 2>/dev/null && oc get -n istio-system route/filebrowser >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo "done"
	@echo "access the file browser at http://`oc get -n istio-system route/filebrowser -o jsonpath='{.spec.host}'`"
	@echo "access the frontend at http://`oc get -n istio-system route/frontend -o jsonpath='{.spec.host}'`"

clean:
	-oc delete -k $(BASE)/yaml/base/frontend/
	-oc delete -k $(BASE)/yaml/base/routes/


ensure-logged-in:
	oc whoami
	@echo 'user is logged in'


image:
	-mkdir -p $(BASE)/docker-cache
	docker buildx use $(BUILDERNAME) || docker buildx create --name $(BUILDERNAME) --use
	docker buildx build \
	  --push \
	  --platform=linux/amd64,linux/arm64 \
	  --cache-to type=local,dest=$(BASE)/docker-cache,mode=max \
	  --cache-from type=local,src=$(BASE)/docker-cache \
	  --rm \
	  -t $(IMAGE) \
	  $(BASE)/frontend
	#docker build \
	#  --rm \
	#  -t $(IMAGE) \
	#  $(BASE)/frontend
