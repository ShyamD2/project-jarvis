output "event_bus_arn" {
  value       = aws_cloudwatch_event_bus.jarvis_bus.arn
  description = "ARN of the Jarvis EventBridge Bus"
}

output "event_bus_name" {
  value       = aws_cloudwatch_event_bus.jarvis_bus.name
  description = "Name of the Jarvis EventBridge Bus"
}

output "events_queue_url" {
  value       = aws_sqs_queue.jarvis_events_queue.id
  description = "URL of the primary events SQS queue"
}

output "events_queue_arn" {
  value       = aws_sqs_queue.jarvis_events_queue.arn
  description = "ARN of the primary events SQS queue"
}

output "dlq_url" {
  value       = aws_sqs_queue.jarvis_dlq.id
  description = "URL of the Dead Letter Queue"
}
