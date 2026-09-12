output "world_model_table_name" {
  value       = aws_dynamodb_table.world_model.name
  description = "DynamoDB World Model Table Name"
}

output "world_model_table_arn" {
  value       = aws_dynamodb_table.world_model.arn
  description = "DynamoDB World Model Table ARN"
}

output "action_audit_table_name" {
  value       = aws_dynamodb_table.action_audit.name
  description = "DynamoDB Action Audit Table Name"
}

output "action_audit_table_arn" {
  value       = aws_dynamodb_table.action_audit.arn
  description = "DynamoDB Action Audit Table ARN"
}

output "artifacts_bucket_name" {
  value       = aws_s3_bucket.artifacts.id
  description = "S3 Artifacts Bucket Name"
}

output "artifacts_bucket_arn" {
  value       = aws_s3_bucket.artifacts.arn
  description = "S3 Artifacts Bucket ARN"
}
