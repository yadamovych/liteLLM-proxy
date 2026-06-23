# Deployment features

Reusable Kubernetes deployment modules for the SaaS platform. Each feature under `k8s/<name>/` provides:

- `feature.yaml` — metadata, dependencies, and defaults
- `terraform/module/` — Helm release and supporting Kubernetes/AWS resources
- `terraform/env-template/` — snippet wired into environment-level Terraform
- `helm/values.yaml` — reference Helm values

Environment stacks include features via shared templates in `shared/templates/env/`.

## Available features

| Feature | Path | Description |
|---------|------|-------------|
| LiteLLM | [k8s/litellm](k8s/litellm) | OpenAI-compatible Bedrock proxy with auto routing |

## Usage

Point your environment Terraform at this directory:

```hcl
deployment_features_root = "${path.root}/../../deployment-features"
```

Then include the feature's `terraform/env-template/*.tf` file from your env templates folder.
