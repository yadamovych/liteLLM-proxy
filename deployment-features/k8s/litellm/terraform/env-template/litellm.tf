# LiteLLM K8s feature — env-level wiring template
#
# Copy or render this file into your environment stack, e.g.:
#   ~/projects/saas/infrastructure/environments/<env>/templates/litellm.tf
#
# Requires shared cluster outputs: oidc_provider_arn, oidc_provider_url, postgres

locals {
  litellm_enabled = try(var.features.litellm.enabled, false)
  litellm_image   = try(var.features.litellm.image, {})
}

module "litellm_irsa" {
  source = "${var.deployment_features_root}/k8s/litellm/terraform/irsa"

  enabled             = local.litellm_enabled
  cluster_name        = var.cluster_name
  oidc_provider_arn   = module.eks.oidc_provider_arn
  oidc_provider_url   = replace(module.eks.oidc_provider_url, "https://", "")
  namespace           = try(var.features.litellm.namespace, "litellm")
  service_account_name = try(var.features.litellm.service_account_name, "litellm")
  tags                = var.tags
}

module "litellm" {
  source = "${var.deployment_features_root}/k8s/litellm/terraform/module"

  enabled      = local.litellm_enabled
  environment  = var.environment
  cluster_name = var.cluster_name

  image_repository = try(local.litellm_image.repository, var.container_registry)
  image_tag        = try(local.litellm_image.tag, var.litellm_image_tag)

  aws_region = var.aws_region
  service_account_annotations = module.litellm_irsa.service_account_annotations

  database_endpoint            = module.postgres.writer_endpoint
  database_secret_name         = module.postgres.credentials_secret_name
  database_secret_password_key = "password"

  master_key_secret_name = try(var.features.litellm.master_key_secret_name, "")
  ui_password_secret_name = try(var.features.litellm.ui_password_secret_name, module.postgres.credentials_secret_name)

  ingress_enabled = try(var.features.litellm.ingress.enabled, var.ingress_enabled)
  ingress_host    = try(var.features.litellm.ingress.host, "litellm.${var.domain}")
  ingress_class_name = try(var.features.litellm.ingress.class_name, var.ingress_class_name)
  ingress_tls_secret_name = try(var.features.litellm.ingress.tls_secret_name, "${var.environment}-litellm-tls")

  replica_count = try(var.features.litellm.replica_count, 1)

  proxy_config = try(var.features.litellm.proxy_config, null)
  extra_helm_values = try(var.features.litellm.extra_helm_values, "")

  labels = merge(var.labels, {
    feature = "litellm"
  })

  depends_on = [
    module.litellm_irsa,
    module.postgres,
  ]
}
