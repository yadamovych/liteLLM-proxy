# Attach LiteLLM feature module from deployment-features.
# Include this file from environment-level Terraform after cluster and postgres modules.

variable "deployment_features_root" {
  description = "Absolute or repo-relative path to deployment-features (e.g. ~/projects/saas/deployment-features)."
  type        = string
}

variable "features" {
  description = "Per-environment feature toggles and overrides."
  type        = any
  default     = {}
}

variable "litellm_image_tag" {
  description = "Image tag for the custom LiteLLM proxy build."
  type        = string
  default     = "latest"
}

# See k8s/litellm/terraform/env-template/litellm.tf for module wiring.
