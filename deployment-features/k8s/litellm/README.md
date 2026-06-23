# LiteLLM Kubernetes deployment feature

Deploys the custom [liteLLM-proxy](https://github.com/yadamovych/liteLLM-proxy) image to Kubernetes with Bedrock IRSA, external Postgres, disk cache PVC, and the `bedrock-auto` keyword router.

Follows the same layout as other `deployment-features/k8s/*` modules (e.g. VictoriaMetrics): a Terraform module, Helm values, and env-level template wiring.

## Layout

```
deployment-features/k8s/litellm/
  feature.yaml                 # feature metadata and defaults
  helm/values.yaml             # reference Helm values
  terraform/
    module/                    # helm_release + namespace + secrets + cache PVC
    irsa/                      # EKS IRSA role for Bedrock
    env-template/litellm.tf    # copy into environment stack
```

Shared env templates live under `deployment-features/shared/templates/env/`.

## Prerequisites

- EKS cluster with Helm and Kubernetes Terraform providers configured
- External Postgres (CloudNativePG or RDS) with credentials in a Kubernetes secret
- Container image built from this repo's `Dockerfile` and pushed to your registry
- Bedrock model access in the target AWS account/region

## Environment wiring

1. Set `deployment_features_root` in your environment stack to point at this repo path:

   ```hcl
   deployment_features_root = "${path.root}/../../deployment-features"
   ```

2. Copy or include `terraform/env-template/litellm.tf` into your env templates directory:

   ```
   ~/projects/saas/infrastructure/environments/<env>/templates/litellm.tf
   ```

3. Enable the feature in your env config (see `shared/templates/env/litellm.yaml.tpl`):

   ```yaml
   features:
     litellm:
       enabled: true
       image:
         repository: 123456789012.dkr.ecr.eu-central-1.amazonaws.com/litellm-proxy
         tag: "8bc3158"
       ingress:
         enabled: true
         host: litellm.example.com
   ```

4. Apply the environment Terraform stack.

## What the module creates

| Resource | Purpose |
|----------|---------|
| `kubernetes_namespace` | `litellm` namespace (optional) |
| `kubernetes_secret` | Auto-generated master key when not supplied |
| `kubernetes_persistent_volume_claim` | Disk cache at `/app/.litellm_cache` |
| `helm_release` | Official [litellm-helm](https://github.com/BerriAI/litellm/tree/main/deploy/charts/litellm-helm) chart with custom image + config |
| `aws_iam_role` (irsa submodule) | Bedrock invoke permissions via IRSA |

## Custom image

Build and push from the repo root:

```bash
docker build -t "$REGISTRY/litellm-proxy:$TAG" .
docker push "$REGISTRY/litellm-proxy:$TAG"
```

The image includes:

- `bedrock-auto` keyword complexity router (`src/core/router.py`)
- Bedrock prompt cache + cost footer callbacks (`src/callbacks/`)
- `litellm_config.yaml` defaults (overridable via `proxy_config` variable)

## AWS credentials

Local Docker mounts `~/.aws`. On EKS, use the `terraform/irsa` submodule — it creates a role trusted by the LiteLLM service account with Bedrock invoke permissions. Pass the returned annotations into the main module via `service_account_annotations`.

## Database

The module expects an existing Postgres instance. Set:

- `database_endpoint` — writer hostname
- `database_secret_name` — secret with `username` and `password` keys

Prisma migrations run via the chart's `migrationJob` on install/upgrade.

## Ingress

Set `ingress_enabled = true` and `ingress_host` to expose the proxy and admin UI. TLS is optional via `ingress_tls_secret_name`.

## Outputs

| Output | Description |
|--------|-------------|
| `release_name` | Helm release name |
| `namespace` | Target namespace |
| `service_name` | In-cluster service DNS label |
| `master_key_secret_name` | Secret holding `LITELLM_MASTER_KEY` |

## Comparison with VictoriaMetrics feature

| Aspect | VictoriaMetrics | LiteLLM |
|--------|-----------------|---------|
| Chart source | `victoriametrics.github.io/helm-charts` | `berriai.github.io/litellm-helm` |
| IRSA | Usually none | Bedrock invoke role |
| Persistence | TSDB PVC | Disk cache PVC + external Postgres |
| Env template | `features.victoriametrics` | `features.litellm` |
