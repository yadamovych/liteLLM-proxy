resource "kubernetes_namespace" "litellm" {
  count = var.enabled && var.create_namespace ? 1 : 0

  metadata {
    name = var.namespace
    labels = local.common_labels
  }
}

resource "kubernetes_secret" "master_key" {
  count = var.enabled && var.master_key_secret_name == "" ? 1 : 0

  metadata {
    name      = local.master_key_secret_name
    namespace = var.namespace
    labels    = local.common_labels
  }

  data = {
    (var.master_key_secret_key) = "sk-${random_password.master_key[0].result}"
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace.litellm]
}

resource "random_password" "master_key" {
  count = var.enabled && var.master_key_secret_name == "" ? 1 : 0

  length  = 32
  special = false
}

resource "helm_release" "litellm" {
  count = var.enabled ? 1 : 0

  name             = var.name
  repository       = "https://berriai.github.io/litellm-helm"
  chart            = "litellm-helm"
  version          = var.chart_version
  namespace        = var.namespace
  create_namespace = false
  timeout          = var.helm_timeout
  wait             = true

  values = compact([
    local.helm_values,
    var.extra_helm_values != "" ? var.extra_helm_values : null,
  ])

  depends_on = [
    kubernetes_namespace.litellm,
    kubernetes_secret.master_key,
  ]
}

resource "kubernetes_persistent_volume_claim" "cache" {
  count = var.enabled && var.cache_persistence_enabled ? 1 : 0

  metadata {
    name      = "${var.name}-cache"
    namespace = var.namespace
    labels    = local.common_labels
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = var.cache_storage_size
      }
    }
    storage_class_name = var.cache_storage_class != "" ? var.cache_storage_class : null
  }

  depends_on = [kubernetes_namespace.litellm]
}
