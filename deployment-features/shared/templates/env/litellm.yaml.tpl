# Shared env template fragment for LiteLLM
# Render with your env templating tool (e.g. scripts/render-templates.ps1 pattern)

features:
  litellm:
    enabled: ${litellm_enabled}
    namespace: litellm
    replica_count: ${litellm_replica_count}
    image:
      repository: ${litellm_image_repository}
      tag: ${litellm_image_tag}
    ingress:
      enabled: ${litellm_ingress_enabled}
      host: litellm.${domain}
      class_name: nginx
      tls_secret_name: ${environment}-litellm-tls
    # Optional override of proxy_config (defaults to bedrock-auto stack from feature module)
    # proxy_config: {}
