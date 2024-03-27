# OpenShift AI / KServe / vLLM

This repo deploys an LLM using KServe and vLLM.

## Setup

01. Provision an `AWS Blank Open Environment` in `ap-southeast-1`, create an OpenShift cluster with at least 1 `p3.8xlarge` worker node (this is needed because we are using the 34b-parameter LLaVA model)

	*   Create a new directory for the install files

			mkdir demo

			cd demo

	*   Generate `install-config.yaml`

			openshift-install create install-config

	*   Set the compute pool to 2 replica with `p3.2xlarge` intances, and set the control plane to a single master (you will need to have `yq` installed)

			mv install-config.yaml install-config-old.yaml

			yq '.compute[0].replicas=2' < install-config-old.yaml \
			| \
			yq '.compute[0].platform = {"aws":{"zones":["ap-southeast-1b"], "type":"p3.2xlarge"}}' \
			| \
			yq '.controlPlane.replicas=1' \
			> install-config.yaml

	*   Create the cluster

			openshift-install create cluster

01. Set the `KUBECONFIG` environment variable to point to the new cluster

01. Deploy all components to OpenShift

		make deploy
	
	This will:
	
	*   Deploy the NFD and Nvidia GPU operators
	*   Deploy the OpenShift Serverless and Service Mesh operators
	*   Deploy OpenShift AI and KServe
	*   Deploy minio and upload a model to a bucket in minio
	*   Deploy the `InferenceService`


## Testing the LLM

01. Get the status of the LLM

		oc get -n demo inferenceservice/llm

01. Get info about the model

		llm_url="$(oc get -n demo inferenceservice/llm -o jsonpath='{.status.url}')"

		curl -k ${llm_url}/v1/models

01. Chat with the LLM

		cat << EOF \
		| \
		curl ${llm_url}/v1/chat/completions \
		  -sk \
		  -H 'Content-Type: application/json' \
		  -d @- \
		| \
		jq
		{
		  "model":"/mnt/models",
		  "messages":[
		    {
		      "role":"system",
		      "content":"You are a helpful assistant."
		    },
		    {
		      "role":"user",
		      "content":"Why is the sky blue?"
		    }
		  ]
		}
		EOF


## Accessing Minio

*   Get the URL of the minio console with

		make minio-console

*   Login to the console with `minio` / `minio123`


## Troubleshooting

*   Sometimes OpenShift takes too long to pull the vllm image and it times out and the revision is considered failed - when this happens, list the revision with `oc get revisions` and delete the revision


## Resources

*   [Custom ServingRuntime](https://developer.ibm.com/tutorials/awb-creating-custom-runtimes-in-modelmesh/#create-the-servingruntime-resource)
*   [vLLM with KServe](https://kserve.github.io/website/0.11/modelserving/v1beta1/llm/vllm/)
*   [Deploy InferenceService with a saved model on S3](https://kserve.github.io/website/0.11/modelserving/storage/s3/s3/)
*   [Hugging Face mistral](https://huggingface.co/mistralai/Mistral-7B-v0.1)
*   [Minio CLI](https://min.io/docs/minio/linux/reference/minio-mc-admin.html)
