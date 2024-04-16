PROJ=demo
S3_IMAGE=ghcr.io/kwkoo/s3-utils
BUILDERNAME=multiarch-builder

BASE:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


.PHONY: deploy
deploy: ensure-logged-in configure-user-workload-monitoring deploy-nvidia deploy-kserve-dependencies deploy-oai deploy-minio upload-model deploy-llm
	@echo "installation complete"


.PHONY: ensure-logged-in
ensure-logged-in:
	oc whoami
	@echo 'user is logged in'


.PHONY: configure-user-workload-monitoring
configure-user-workload-monitoring:
	if [ `oc get -n openshift-monitoring cm/cluster-monitoring-config --no-headers 2>/dev/null | wc -l` -lt 1 ]; then \
	  echo 'enableUserWorkload: true' > /tmp/config.yaml; \
	  oc create -n openshift-monitoring cm cluster-monitoring-config --from-file=/tmp/config.yaml; \
	  rm -f /tmp/config.yaml; \
	fi


.PHONY: deploy-nfd
deploy-nfd: ensure-logged-in
	@echo "deploying NodeFeatureDiscovery operator..."
	oc apply -f $(BASE)/yaml/operators/nfd-operator.yaml
	@/bin/echo -n 'waiting for NodeFeatureDiscovery CRD...'
	@until oc get crd nodefeaturediscoveries.nfd.openshift.io >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc apply -f $(BASE)/yaml/operators/nfd-cr.yaml
	@/bin/echo -n 'waiting for nodes to be labelled...'
	@while [ `oc get nodes --no-headers -l 'feature.node.kubernetes.io/pci-10de.present=true' 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	@echo 'NFD operator installed successfully'


.PHONY: deploy-nvidia
deploy-nvidia: deploy-nfd
	@echo "deploying nvidia GPU operator..."
	oc apply -f $(BASE)/yaml/operators/nvidia-operator.yaml
	@/bin/echo -n 'waiting for ClusterPolicy CRD...'
	@until oc get crd clusterpolicies.nvidia.com >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc apply -f $(BASE)/yaml/operators/cluster-policy.yaml
	@/bin/echo -n 'waiting for nvidia-device-plugin-daemonset...'
	@until oc get -n nvidia-gpu-operator ds/nvidia-device-plugin-daemonset >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo "done"
	@DESIRED="`oc get -n nvidia-gpu-operator ds/nvidia-device-plugin-daemonset -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null`"; \
	if [ "$$DESIRED" -lt 1 ]; then \
	  echo "could not get desired replicas"; \
	  exit 1; \
	fi; \
	echo "desired replicas = $$DESIRED"; \
	/bin/echo -n "waiting for $$DESIRED replicas to be ready..."; \
	while [ "`oc get -n nvidia-gpu-operator ds/nvidia-device-plugin-daemonset -o jsonpath='{.status.numberReady}' 2>/dev/null`" -lt "$$DESIRED" ]; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo "done"
	@echo "checking that worker nodes have access to GPUs..."
	@for po in `oc get po -n nvidia-gpu-operator -o name -l app=nvidia-device-plugin-daemonset`; do \
	  echo "checking $$po"; \
	  oc rsh -n nvidia-gpu-operator $$po nvidia-smi; \
	done


.PHONY: deploy-kserve-dependencies
deploy-kserve-dependencies:
	@echo "deploying OpenShift Serverless..."
	oc apply -f $(BASE)/yaml/operators/serverless-operator.yaml
	@/bin/echo -n 'waiting for KnativeServing CRD...'
	@until oc get crd knativeservings.operator.knative.dev >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	@echo "deploying OpenShift Service Mesh operator..."
	oc apply -f $(BASE)/yaml/operators/service-mesh-operator.yaml
	@/bin/echo -n 'waiting for ServiceMeshControlPlane CRD...'
	@until oc get crd servicemeshcontrolplanes.maistra.io >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'


.PHONY: deploy-oai
deploy-oai:
	@echo "deploying OpenShift AI operator..."
	oc apply -f $(BASE)/yaml/operators/openshift-ai-operator.yaml
	@/bin/echo -n 'waiting for DataScienceCluster CRD...'
	@until oc get crd datascienceclusters.datasciencecluster.opendatahub.io >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc apply -f $(BASE)/yaml/operators/datasciencecluster.yaml
	@/bin/echo -n "waiting for inferenceservice-config ConfigMap to appear..."
	@until oc get -n redhat-ods-applications cm/inferenceservice-config >/dev/null 2>/dev/null; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	@echo "increasing storage initializer memory limit..."
	# modify storageInitializer memory limit - without this, there is a chance
	# that the storageInitializer initContainer will be OOMKilled
	rm -f /tmp/storageInitializer
	oc extract -n redhat-ods-applications cm/inferenceservice-config --to=/tmp --keys=storageInitializer
	cat /tmp/storageInitializer | sed 's/"memoryLimit": .*/"memoryLimit": "4Gi",/' > /tmp/storageInitializer.new
	oc set data -n redhat-ods-applications cm/inferenceservice-config --from-file=storageInitializer=/tmp/storageInitializer.new
	rm -f /tmp/storageInitializer /tmp/storageInitializer.new
	@/bin/echo -n "waiting for ServiceMeshControlPlane to appear..."
	@until oc get -n istio-system smcp/data-science-smcp >/dev/null 2>/dev/null; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"


.PHONY: deploy-minio
deploy-minio:
	@echo "deploying minio..."
	oc create ns $(PROJ) || echo "$(PROJ) namespace exists"
	oc apply -n $(PROJ) -f $(BASE)/yaml/minio.yaml
	@/bin/echo -n "waiting for minio routes..."
	@until oc get -n $(PROJ) route/minio >/dev/null 2>/dev/null && oc get -n $(PROJ) route/minio-console >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo "done"
	oc set env \
	  -n $(PROJ) \
	  sts/minio \
	  MINIO_SERVER_URL="http://`oc get -n $(PROJ) route/minio -o jsonpath='{.spec.host}'`" \
	  MINIO_BROWSER_REDIRECT_URL="http://`oc get -n $(PROJ) route/minio-console -o jsonpath='{.spec.host}'`"


.PHONY: upload-model
upload-model:
	@echo "removing any previous jobs..."
	-oc delete -n $(PROJ) -k $(BASE)/yaml/base/s3-job/
	@/bin/echo -n "waiting for job to go away..."
	@while [ `oc get -n $(PROJ) --no-headers job/setup-s3 2>/dev/null | wc -l` -gt 0 ]; do \
	  /bin/echo -n "."; \
	done
	@echo "done"
	@echo "creating job to upload model to S3..."
	oc apply -n $(PROJ) -k $(BASE)/yaml/base/s3-job/
	@/bin/echo -n "waiting for pod to show up..."
	@while [ `oc get -n $(PROJ) po -l job=setup-s3 --no-headers 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	@/bin/echo "waiting for pod to be ready..."
	oc wait -n $(PROJ) `oc get -n $(PROJ) po -o name -l job=setup-s3` --for=condition=Ready --timeout=300s
	oc logs -n $(PROJ) -f job/setup-s3
	oc delete -n $(PROJ) -k $(BASE)/yaml/base/s3-job/


.PHONY: upload-model-nousllama2
upload-model-nousllama2:
	@echo "removing any previous jobs..."
	-oc delete -n $(PROJ) -k $(BASE)/yaml/overlays/s3-job-nousllama2/
	@/bin/echo -n "waiting for job to go away..."
	@while [ `oc get -n $(PROJ) --no-headers job/setup-s3 2>/dev/null | wc -l` -gt 0 ]; do \
	  /bin/echo -n "."; \
	done
	@echo "done"
	@echo "creating job to upload model to S3..."
	oc apply -n $(PROJ) -k $(BASE)/yaml/overlays/s3-job-nousllama2/
	@/bin/echo -n "waiting for pod to show up..."
	@while [ `oc get -n $(PROJ) po -l job=setup-s3 --no-headers 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	@/bin/echo "waiting for pod to be ready..."
	oc wait -n $(PROJ) `oc get -n $(PROJ) po -o name -l job=setup-s3` --for=condition=Ready
	oc logs -n $(PROJ) -f job/setup-s3
	oc delete -n $(PROJ) -k $(BASE)/yaml/overlays/s3-job-nousllama2/


.PHONY: deploy-llm
deploy-llm:
	@echo "deploying inference service..."
	# inference service
	#
	oc create ns $(PROJ) || echo "$(PROJ) namespace exists"
	@AWS_ACCESS_KEY_ID="`oc extract secret/minio -n $(PROJ) --to=- --keys=MINIO_ROOT_USER 2>/dev/null`" \
	&& \
	AWS_SECRET_ACCESS_KEY="`oc extract secret/minio -n $(PROJ) --to=- --keys=MINIO_ROOT_PASSWORD 2>/dev/null`" \
	&& \
	NS_UID="`oc get ns $(PROJ) -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}' | cut -d / -f 1`" \
	&& \
	INIT_UID=$$(( NS_UID + 1 )) \
	&& \
	echo "AWS_ACCESS_KEY_ID=$$AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY=$$AWS_SECRET_ACCESS_KEY NS_UID=$$NS_UID INIT_UID=$$INIT_UID" \
	&& \
	oc kustomize $(BASE)/yaml/base/inferenceservice/ \
	| \
	sed \
	  -e "s/AWS_ACCESS_KEY_ID: .*/AWS_ACCESS_KEY_ID: $$AWS_ACCESS_KEY_ID/" \
	  -e "s/AWS_SECRET_ACCESS_KEY: .*/AWS_SECRET_ACCESS_KEY: $$AWS_SECRET_ACCESS_KEY/" \
	  -e "s/storage-initializer-uid: .*/storage-initializer-uid: \"$$INIT_UID\"/" \
	| \
	oc apply -n $(PROJ) -f -
	@/bin/echo -n "waiting for inferenceservice to appear..."
	@until oc get -n $(PROJ) inferenceservice/llm >/dev/null 2>/dev/null; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	oc wait -n $(PROJ) inferenceservice/llm --for=condition=Ready --timeout=300s
	oc patch peerauthentication/default \
	  --type json \
	  -p '[{"op":"replace", "path":"/spec/mtls/mode", "value":"PERMISSIVE"}]' \
	  -n $(PROJ)



.PHONY: clean-llm
clean-llm:
	oc delete -n $(PROJ) -k $(BASE)/yaml/base/inferenceservice/ 2>/dev/null || exit 0


.PHONY: deploy-llm-nousllama2
deploy-llm-nousllama2:
	@echo "deploying inference service..."
	# inference service
	#
	oc create ns $(PROJ) || echo "$(PROJ) namespace exists"
	@AWS_ACCESS_KEY_ID="`oc extract secret/minio -n $(PROJ) --to=- --keys=MINIO_ROOT_USER 2>/dev/null`" \
	&& \
	AWS_SECRET_ACCESS_KEY="`oc extract secret/minio -n $(PROJ) --to=- --keys=MINIO_ROOT_PASSWORD 2>/dev/null`" \
	&& \
	NS_UID="`oc get ns $(PROJ) -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}' | cut -d / -f 1`" \
	&& \
	INIT_UID=$$(( NS_UID + 1 )) \
	&& \
	echo "AWS_ACCESS_KEY_ID=$$AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY=$$AWS_SECRET_ACCESS_KEY NS_UID=$$NS_UID INIT_UID=$$INIT_UID" \
	&& \
	oc kustomize $(BASE)/yaml/overlays/inferenceservice-nousllama2/ \
	| \
	sed \
	  -e "s/AWS_ACCESS_KEY_ID: .*/AWS_ACCESS_KEY_ID: $$AWS_ACCESS_KEY_ID/" \
	  -e "s/AWS_SECRET_ACCESS_KEY: .*/AWS_SECRET_ACCESS_KEY: $$AWS_SECRET_ACCESS_KEY/" \
	  -e "s/storage-initializer-uid: .*/storage-initializer-uid: \"$$INIT_UID\"/" \
	| \
	oc apply -n $(PROJ) -f -
	@/bin/echo -n "waiting for inferenceservice to appear..."
	@until oc get -n $(PROJ) inferenceservice/llm >/dev/null 2>/dev/null; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	oc wait -n $(PROJ) inferenceservice/llm --for=condition=Ready --timeout=300s
	oc patch peerauthentication/default \
	  --type json \
	  -p '[{"op":"replace", "path":"/spec/mtls/mode", "value":"PERMISSIVE"}]' \
	  -n $(PROJ)


.PHONY: s3-image
s3-image:
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
	  -t $(S3_IMAGE):amd64 \
	  $(BASE)/s3-utils
	docker buildx build \
	  --push \
	  --provenance false \
	  --sbom false \
	  --platform=linux/arm64 \
	  --cache-to type=local,dest=$(BASE)/docker-cache/arm64,mode=max \
	  --cache-from type=local,src=$(BASE)/docker-cache/arm64 \
	  --rm \
	  -t $(S3_IMAGE):arm64 \
	  $(BASE)/s3-utils
	docker manifest create \
	  $(S3_IMAGE):latest \
	  --amend $(S3_IMAGE):amd64 \
	  --amend $(S3_IMAGE):arm64
	docker manifest push --purge $(S3_IMAGE):latest
	@#docker build --rm -t $(S3_IMAGE) $(BASE)/s3-utils


.PHONY: minio-console
minio-console:
	@echo "http://`oc get -n $(PROJ) route/minio-console -o jsonpath='{.spec.host}'`"


.PHONY: clean-minio
clean-minio:
	oc delete -n $(PROJ) -f $(BASE)/yaml/minio.yaml
	oc delete -n $(PROJ) pvc -l app.kubernetes.io/instance=minio,app.kubernetes.io/name=minio