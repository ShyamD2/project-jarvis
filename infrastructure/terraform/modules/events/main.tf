terraform {
  required_version = ">= 1.5.0"
}

resource "aws_cloudwatch_event_bus" "jarvis_bus" {
  name = var.event_bus_name

  tags = {
    Name        = var.event_bus_name
    Project     = "JARVIS"
    Environment = var.environment
  }
}

# Dead Letter Queue for failed events
resource "aws_sqs_queue" "jarvis_dlq" {
  name                      = "${var.environment}-jarvis-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.environment}-jarvis-dlq"
    Environment = var.environment
  }
}

# Primary Event Buffer Queue
resource "aws_sqs_queue" "jarvis_events_queue" {
  name                      = "${var.environment}-jarvis-events-queue"
  message_retention_seconds = 86400 # 1 day
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jarvis_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Name        = "${var.environment}-jarvis-events-queue"
    Environment = var.environment
  }
}

# EventBridge Rule catching all sensory, agent, and system events
resource "aws_cloudwatch_event_rule" "jarvis_catch_all" {
  name           = "${var.environment}-jarvis-all-events"
  description    = "Capture all Jarvis sensory and system events"
  event_bus_name = aws_cloudwatch_event_bus.jarvis_bus.name

  event_pattern = jsonencode({
    source = [{ prefix = "jarvis" }, { prefix = "sensory" }, { prefix = "agent" }, { prefix = "iot" }]
  })
}

# Target: SQS Queue
resource "aws_cloudwatch_event_target" "sqs_target" {
  rule           = aws_cloudwatch_event_rule.jarvis_catch_all.name
  event_bus_name = aws_cloudwatch_event_bus.jarvis_bus.name
  target_id      = "JarvisEventsSQS"
  arn            = aws_sqs_queue.jarvis_events_queue.arn

  dead_letter_config {
    arn = aws_sqs_queue.jarvis_dlq.arn
  }
}

# SQS Policy allowing EventBridge to send messages
resource "aws_sqs_queue_policy" "sqs_policy" {
  queue_url = aws_sqs_queue.jarvis_events_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.jarvis_events_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.jarvis_catch_all.arn
          }
        }
      }
    ]
  })
}
