output "vpc_id" {
  value       = module.networking.vpc_id
  description = "VPC ID"
}

output "event_bus_name" {
  value       = module.events.event_bus_name
  description = "Jarvis Event Bus Name"
}

output "event_bus_arn" {
  value       = module.events.event_bus_arn
  description = "Jarvis Event Bus ARN"
}

output "events_queue_url" {
  value       = module.events.events_queue_url
  description = "Jarvis Events SQS Queue URL"
}

output "world_model_table" {
  value       = module.memory.world_model_table_name
  description = "World Model DynamoDB Table"
}

output "action_audit_table" {
  value       = module.memory.action_audit_table_name
  description = "Action Audit DynamoDB Table"
}

output "artifacts_bucket" {
  value       = module.memory.artifacts_bucket_name
  description = "Artifacts S3 Bucket"
}

output "jarvis_core_role_arn" {
  value       = module.iam.jarvis_core_role_arn
  description = "Jarvis Core IAM Role ARN"
}
