output "jarvis_core_role_arn" {
  value       = aws_iam_role.jarvis_core_role.arn
  description = "ARN of the Jarvis Core IAM role"
}

output "jarvis_core_role_name" {
  value       = aws_iam_role.jarvis_core_role.name
  description = "Name of the Jarvis Core IAM role"
}
