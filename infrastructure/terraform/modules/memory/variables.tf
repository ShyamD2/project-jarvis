variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
}

variable "aws_account_id" {
  type        = string
  description = "AWS Account ID for globally unique bucket naming"
  default     = "000000000000"
}
