PROJ=demo
VLLM_IMAGE=ghcr.io/kwkoo/vllm-with-chat
S3_IMAGE=ghcr.io/kwkoo/s3-utils
BUILDERNAME=multiarch-builder

BASE:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

.PHONY: deploy ensure-logged-in deploy-nfd deploy-nvidia deploy-kserve-dependencies deploy-oai deploy-minio upload-model deploy-llm vllm-image s3-image minio-console


deploy: ensure-logged-in
	# tdb


ensure-logged-in:
	oc whoami
	@echo 'user is logged in'


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


deploy-kserve-dependencies:
	@echo "deploying OpenShift Serverless..."
	oc apply -f $(BASE)/yaml/operators/serverless-operator.yaml
	@/bin/echo -n 'waiting for KnativeServing CRD...'
	@until oc get crd knativeservings.operator.knative.dev >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	@echo "deploying Elasticsearch operator..."
	oc apply -f $(BASE)/yaml/operators/elasticsearch-operator.yaml
	@/bin/echo -n 'waiting for elasticsearch operator pod...'
	@while [ `oc get po -n openshift-operators-redhat -l name=elasticsearch-operator --no-headers 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc wait -n openshift-operators-redhat po -l name=elasticsearch-operator --for condition=Ready
	@echo "deploying distributed tracing operator..."
	oc apply -f $(BASE)/yaml/operators/distributed-tracing-operator.yaml
	@/bin/echo -n 'waiting for distributed tracing operator pod...'
	@while [ `oc get po -n openshift-distributed-tracing --no-headers -l name=jaeger-operator 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc wait -n openshift-distributed-tracing po -l name=jaeger-operator --for condition=Ready
	@echo "deploying kiali operator..."
	@EXISTING="`oc get -n openshift-operators operatorgroup/global-operators -o jsonpath='{.metadata.annotations.olm\.providedAPIs}' 2>/dev/null`"; \
	if [ -z "$$EXISTING" ]; then \
	  oc annotate -n openshift-operators operatorgroup/global-operators olm.providedAPIs=Kiali.v1alpha1.kiali.io; \
	else \
	  echo $$EXISTING | grep Kiali; \
	  if [ $$? -ne 0 ]; then \
	    oc annotate --overwrite -n openshift-operators operatorgroup/global-operators olm.providedAPIs="$$EXISTING,Kiali.v1alpha1.kiali.io"; \
	  fi; \
	fi
	oc apply -f $(BASE)/yaml/operators/kiali-operator.yaml
	@/bin/echo -n 'waiting for kiali operator pod...'
	@while [ `oc get po -n openshift-operators --no-headers -l app=kiali-operator 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc wait -n openshift-operators po -l app=kiali-operator --for condition=Ready
	@echo "deploying OpenShift Service Mesh operator..."
	@EXISTING="`oc get -n openshift-operators operatorgroup/global-operators -o jsonpath='{.metadata.annotations.olm\.providedAPIs}' 2>/dev/null`"; \
	if [ -z "$$EXISTING" ]; then \
	  oc annotate -n openshift-operators operatorgroup/global-operators olm.providedAPIs=ServiceMeshControlPlane.v2.maistra.io,ServiceMeshMember.v1.maistra.io,ServiceMeshMemberRoll.v1.maistra.io; \
	else \
	  echo $$EXISTING | grep ServiceMeshControlPlane; \
	  if [ $$? -ne 0 ]; then \
	    oc annotate --overwrite -n openshift-operators operatorgroup/global-operators olm.providedAPIs="$$EXISTING,ServiceMeshControlPlane.v2.maistra.io,ServiceMeshMember.v1.maistra.io,ServiceMeshMemberRoll.v1.maistra.io"; \
	  fi; \
	fi
	oc apply -f $(BASE)/yaml/operators/service-mesh-operator.yaml
	@/bin/echo -n 'waiting for ServiceMeshControlPlane CRD...'
	@until oc get crd servicemeshcontrolplanes.maistra.io >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'


deploy-oai:
	oc apply -f $(BASE)/yaml/operators/openshift-ai-operator.yaml
	@/bin/echo -n 'waiting for DataScienceCluster CRD...'
	@until oc get crd datascienceclusters.datasciencecluster.opendatahub.io >/dev/null 2>/dev/null; do \
	  /bin/echo -n '.'; \
	  sleep 5; \
	done
	@echo 'done'
	oc apply -f $(BASE)/yaml/operators/datasciencecluster.yaml

deploy-minio:
	-oc create ns $(PROJ)
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
	  MINIO_SERVER_URL="http://`oc get route/minio -o jsonpath='{.spec.host}'`" \
	  MINIO_BROWSER_REDIRECT_URL="http://`oc get route/minio-console -o jsonpath='{.spec.host}'`"

upload-model:
	oc apply -n $(PROJ) -f $(BASE)/yaml/s3-job.yaml
	@/bin/echo -n "waiting for pod to show up..."
	@while [ `oc get -n $(PROJ) po -l job=setup-s3 --no-headers 2>/dev/null | wc -l` -lt 1 ]; do \
	  /bin/echo -n "."; \
	  sleep 5; \
	done
	@echo "done"
	@/bin/echo "waiting for pod to be ready..."
	oc wait -n $(PROJ) `oc get -n $(PROJ) po -o name -l job=setup-s3` --for=condition=Ready
	oc logs -n $(PROJ) -f job/setup-s3
	oc delete -n $(PROJ) -f $(BASE)/yaml/s3-job.yaml

deploy-llm:
	# modify storageInitializer memory limit - without this, there is a chance
	# that the storageInitializer initContainer will be OOMKilled
	rm -f /tmp/storageInitializer
	oc extract -n redhat-ods-applications cm/inferenceservice-config --to=/tmp --keys=storageInitializer
	cat /tmp/storageInitializer | sed 's/"memoryLimit": .*/"memoryLimit": "4Gi",/' > /tmp/storageInitializer.new
	oc set data -n redhat-ods-applications cm/inferenceservice-config --from-file=storageInitializer=/tmp/storageInitializer.new
	rm -f /tmp/storageInitializer /tmp/storageInitializer.new

	# inference service
	#
	-oc create ns $(PROJ)
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
	sed \
	  -e "s/AWS_ACCESS_KEY_ID: .*/AWS_ACCESS_KEY_ID: $$AWS_ACCESS_KEY_ID/" \
	  -e "s/AWS_SECRET_ACCESS_KEY: .*/AWS_SECRET_ACCESS_KEY: $$AWS_SECRET_ACCESS_KEY/" \
	  -e "s/storage-initializer-uid: .*/storage-initializer-uid: \"$$INIT_UID\"/" \
	  $(BASE)/yaml/inference.yaml \
	| oc apply -n $(PROJ) -f -


vllm-image:
	docker build -t $(VLLM_IMAGE) $(BASE)/vllm-image/
	docker push $(VLLM_IMAGE)

s3-image:
	-mkdir -p $(BASE)/docker-cache
	docker buildx use $(BUILDERNAME) || docker buildx create --name $(BUILDERNAME) --use
	docker buildx build \
	  --push \
	  --platform=linux/amd64,linux/arm64 \
	  --cache-to type=local,dest=$(BASE)/docker-cache,mode=max \
	  --cache-from type=local,src=$(BASE)/docker-cache \
	  --rm \
	  -t $(S3_IMAGE) \
	  $(BASE)/s3-utils
	#docker build --rm -t $(S3_IMAGE) $(BASE)/s3-utils

minio-console:
	@echo "http://`oc get -n $(PROJ) route/minio-console -o jsonpath='{.spec.host}'`"
