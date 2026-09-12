variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
}

variable "event_bus_arn" {
  type        = string
  description = "ARN of the Jarvis Event Bus"
}

variable "events_queue_arn" {
  type        = string
  description = "ARN of the primary events SQS queue"
}

variable "world_model_table_arn" {
  type        = string
  description = "ARN of the World Model DynamoDB table"
}

variable "action_audit_table_arn" {
  type        = string
  description = "ARN of the Action Audit DynamoDB table"
}
