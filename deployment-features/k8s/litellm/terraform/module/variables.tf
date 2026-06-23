variable "enabled" {
  description = "Enable LiteLLM deployment."
  type        = bool
  default     = true
}

variable "name" {
  description = "Helm release name."
  type        = string
  default     = "litellm"
}

variable "namespace" {
  description = "Kubernetes namespace for LiteLLM."
  type        = string
  default     = "litellm"
}

variable "create_namespace" {
  description = "Create the target namespace if it does not exist."
  type        = bool
  default     = true
}

variable "environment" {
  description = "Environment label (dev, staging, prod)."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name used for tagging and IRSA trust policy."
  type        = string
}

variable "chart_version" {
  description = "Pinned litellm-helm chart version."
  type        = string
  default     = "0.4.0"
}

variable "image_repository" {
  description = "Container image repository for the custom LiteLLM proxy build."
  type        = string
}

variable "image_tag" {
  description = "Container image tag."
  type        = string
  default     = "latest"
}

variable "image_pull_policy" {
  description = "Kubernetes image pull policy."
  type        = string
  default     = "IfNotPresent"
}

variable "replica_count" {
  description = "Number of LiteLLM proxy replicas."
  type        = number
  default     = 1
}

variable "aws_region" {
  description = "AWS region for Bedrock calls."
  type        = string
}

variable "service_account_annotations" {
  description = "Annotations for the LiteLLM service account (typically IRSA role ARN)."
  type        = map(string)
  default     = {}
}

variable "database_endpoint" {
  description = "Postgres host for LiteLLM (writer endpoint)."
  type        = string
}

variable "database_name" {
  description = "Postgres database name."
  type        = string
  default     = "litellm"
}

variable "database_username" {
  description = "Postgres username."
  type        = string
  default     = "litellm"
}

variable "database_secret_name" {
  description = "Kubernetes secret containing database credentials."
  type        = string
}

variable "database_secret_password_key" {
  description = "Key in the database secret that holds the password."
  type        = string
  default     = "password"
}

variable "master_key_secret_name" {
  description = "Kubernetes secret containing LITELLM_MASTER_KEY."
  type        = string
  default     = ""
}

variable "master_key_secret_key" {
  description = "Key in the master key secret."
  type        = string
  default     = "master-key"
}

variable "ui_username" {
  description = "Admin UI username."
  type        = string
  default     = "admin"
}

variable "ui_password_secret_name" {
  description = "Secret containing the admin UI password."
  type        = string
  default     = ""
}

variable "ui_password_secret_key" {
  description = "Key in the UI password secret."
  type        = string
  default     = "password"
}

variable "ingress_enabled" {
  description = "Expose LiteLLM through an Ingress."
  type        = bool
  default     = false
}

variable "ingress_class_name" {
  description = "Ingress class name."
  type        = string
  default     = "nginx"
}

variable "ingress_host" {
  description = "Hostname for the LiteLLM ingress."
  type        = string
  default     = ""
}

variable "ingress_tls_secret_name" {
  description = "TLS secret for ingress when TLS is enabled."
  type        = string
  default     = ""
}

variable "cache_persistence_enabled" {
  description = "Enable a PVC for LiteLLM disk cache."
  type        = bool
  default     = true
}

variable "cache_storage_size" {
  description = "PVC size for disk cache."
  type        = string
  default     = "5Gi"
}

variable "cache_storage_class" {
  description = "Storage class for the cache PVC."
  type        = string
  default     = ""
}

variable "litellm_cost_footer" {
  description = "Append cost footer to chat responses."
  type        = bool
  default     = true
}

variable "litellm_prompt_cache" {
  description = "Enable Bedrock prompt caching."
  type        = bool
  default     = true
}

variable "litellm_log_level" {
  description = "LiteLLM log level."
  type        = string
  default     = "WARNING"
}

variable "proxy_config" {
  description = "LiteLLM proxy_config map rendered into config.yaml."
  type        = any
  default     = null
}

variable "extra_helm_values" {
  description = "Additional Helm values YAML merged on top of the module defaults."
  type        = string
  default     = ""
}

variable "helm_timeout" {
  description = "Helm install/upgrade timeout in seconds."
  type        = number
  default     = 600
}

variable "labels" {
  description = "Common labels applied to created resources."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags propagated to AWS resources created by this module."
  type        = map(string)
  default     = {}
}
