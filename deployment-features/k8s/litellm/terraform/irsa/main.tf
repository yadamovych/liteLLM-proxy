terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
}

variable "enabled" {
  description = "Enable IRSA for LiteLLM Bedrock access."
  type        = bool
  default     = true
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider."
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider (without https://)."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where LiteLLM runs."
  type        = string
  default     = "litellm"
}

variable "service_account_name" {
  description = "Kubernetes service account name used by LiteLLM."
  type        = string
  default     = "litellm"
}

variable "bedrock_policy_arn" {
  description = "Optional managed policy ARN for Bedrock access. When empty, an inline policy is created."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags for IAM resources."
  type        = map(string)
  default     = {}
}

resource "aws_iam_role" "litellm" {
  count = var.enabled ? 1 : 0

  name = "${var.cluster_name}-litellm-bedrock"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:${var.namespace}:${var.service_account_name}"
            "${var.oidc_provider_url}:aud" = "sts.amazonaws.com"
          }
        }
      },
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "bedrock" {
  count = var.enabled && var.bedrock_policy_arn == "" ? 1 : 0

  name = "bedrock-invoke"
  role = aws_iam_role.litellm[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:Converse",
          "bedrock:ConverseStream",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_managed" {
  count = var.enabled && var.bedrock_policy_arn != "" ? 1 : 0

  role       = aws_iam_role.litellm[0].name
  policy_arn = var.bedrock_policy_arn
}

output "role_arn" {
  description = "IAM role ARN for LiteLLM IRSA."
  value       = var.enabled ? aws_iam_role.litellm[0].arn : null
}

output "service_account_annotations" {
  description = "Annotations to pass into the LiteLLM Helm module."
  value = var.enabled ? {
    "eks.amazonaws.com/role-arn" = aws_iam_role.litellm[0].arn
  } : {}
}
