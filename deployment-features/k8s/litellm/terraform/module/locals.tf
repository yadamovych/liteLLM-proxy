locals {
  common_labels = merge(
    {
      "app.kubernetes.io/name"       = "litellm"
      "app.kubernetes.io/instance"   = var.name
      "app.kubernetes.io/managed-by" = "terraform"
      "environment"                  = var.environment
    },
    var.labels,
  )

  master_key_secret_name = var.master_key_secret_name != "" ? var.master_key_secret_name : "${var.name}-master-key"
  ui_password_secret_name = var.ui_password_secret_name != "" ? var.ui_password_secret_name : "${var.name}-ui-password"

  default_proxy_config = {
    model_list = [
      {
        model_name = "claude-sonnet-4.6"
        litellm_params = {
          model = "bedrock/eu.anthropic.claude-sonnet-4-6"
        }
        model_info = {
          supports_prompt_caching = true
          max_input_tokens        = 200000
          max_output_tokens       = 64000
        }
      },
      {
        model_name = "claude-haiku"
        litellm_params = {
          model = "bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0"
        }
        model_info = {
          supports_prompt_caching = true
          max_input_tokens        = 200000
          max_output_tokens       = 16000
        }
      },
      {
        model_name = "qwen3-coder"
        litellm_params = {
          model = "bedrock/qwen.qwen3-coder-30b-a3b-v1:0"
        }
        model_info = {
          max_input_tokens  = 262144
          max_output_tokens = 8192
        }
      },
      {
        model_name = "bedrock-auto"
        litellm_params = {
          model                           = "auto_router/complexity_router"
          complexity_router_default_model = "qwen3-coder"
          complexity_router_config = {
            tiers = {
              SIMPLE    = "qwen3-coder"
              MEDIUM    = "claude-haiku"
              COMPLEX   = "claude-sonnet"
              REASONING = "claude-sonnet"
            }
            default_model = "qwen3-coder"
          }
        }
        model_info = {
          supports_prompt_caching = true
        }
      },
    ]

    router_settings = {
      routing_strategy          = "simple-shuffle"
      optional_pre_call_checks  = ["prompt_caching"]
    }

    litellm_settings = {
      set_verbose = false
      default_key_generate_params = {
        models = [
          "bedrock-auto",
          "claude-haiku",
          "claude-sonnet",
          "qwen3-coder",
        ]
        max_budget      = 30
        budget_duration = "30d"
      }
      cache = true
      cache_params = {
        type           = "disk"
        disk_cache_dir = "/app/.litellm_cache"
        ttl            = 3600
        supported_call_types = [
          "completion",
          "acompletion",
        ]
      }
      callbacks = ["callbacks.handler.proxy_handler_instance"]
    }

    general_settings = {
      master_key   = "os.environ/LITELLM_MASTER_KEY"
      database_url = "os.environ/DATABASE_URL"
    }
  }

  proxy_config = var.proxy_config != null ? var.proxy_config : local.default_proxy_config

  helm_values = templatefile("${path.module}/values.yaml.tpl", {
    name                      = var.name
    namespace                 = var.namespace
    environment               = var.environment
    image_repository          = var.image_repository
    image_tag                 = var.image_tag
    image_pull_policy         = var.image_pull_policy
    replica_count             = var.replica_count
    aws_region                = var.aws_region
    service_account_annotations_yaml = indent(4, trimspace(yamlencode(var.service_account_annotations)))
    database_endpoint         = var.database_endpoint
    database_name             = var.database_name
    database_username         = var.database_username
    database_secret_name      = var.database_secret_name
    database_secret_password_key = var.database_secret_password_key
    master_key_secret_name    = local.master_key_secret_name
    master_key_secret_key     = var.master_key_secret_key
    ui_username               = var.ui_username
    ui_password_secret_name   = local.ui_password_secret_name
    ui_password_secret_key    = var.ui_password_secret_key
    ingress_enabled           = var.ingress_enabled
    ingress_class_name        = var.ingress_class_name
    ingress_host              = var.ingress_host
    ingress_tls_secret_name   = var.ingress_tls_secret_name
    cache_persistence_enabled = var.cache_persistence_enabled
    cache_storage_size        = var.cache_storage_size
    cache_storage_class       = var.cache_storage_class
    litellm_cost_footer       = var.litellm_cost_footer
    litellm_prompt_cache      = var.litellm_prompt_cache
    litellm_log_level         = var.litellm_log_level
    proxy_config_yaml         = indent(2, yamlencode(local.proxy_config))
    labels_yaml               = indent(2, trimspace(yamlencode(local.common_labels)))
  })
}
