variable "environment" {
  type        = string
  description = "Environment identifier"
  default     = "dev"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "use_localstack" {
  type        = bool
  description = "Whether to use LocalStack for local emulation"
  default     = true
}

variable "localstack_endpoint" {
  type        = string
  description = "Endpoint URL for LocalStack"
  default     = "http://localhost:4566"
}

variable "aws_account_id" {
  type        = string
  description = "AWS Account ID"
  default     = "000000000000"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.0.0.0/16"
}
