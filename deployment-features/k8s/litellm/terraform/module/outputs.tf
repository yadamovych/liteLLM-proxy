output "release_name" {
  description = "Helm release name."
  value       = var.enabled ? helm_release.litellm[0].name : null
}

output "namespace" {
  description = "Kubernetes namespace."
  value       = var.namespace
}

output "service_name" {
  description = "Kubernetes service name for in-cluster access."
  value       = var.enabled ? "${var.name}-litellm-helm" : null
}

output "service_port" {
  description = "LiteLLM proxy port."
  value       = 4000
}

output "master_key_secret_name" {
  description = "Secret containing the LiteLLM master key."
  value       = local.master_key_secret_name
  sensitive   = true
}

output "ingress_host" {
  description = "Configured ingress host when enabled."
  value       = var.ingress_enabled ? var.ingress_host : null
}

output "irsa_role_arn" {
  description = "IRSA role ARN when created by the companion irsa submodule."
  value       = try(var.service_account_annotations["eks.amazonaws.com/role-arn"], null)
}
