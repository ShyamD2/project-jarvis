terraform {
  required_version = ">= 1.5.0"
}

# Assume role policy for ECS/EC2/Lambda or Local service
data "aws_iam_policy_document" "jarvis_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com", "lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "jarvis_core_role" {
  name               = "${var.environment}-jarvis-core-role"
  assume_role_policy = data.aws_iam_policy_document.jarvis_assume_role.json

  tags = {
    Name        = "${var.environment}-jarvis-core-role"
    Project     = "JARVIS"
    Environment = var.environment
  }
}

# Least-privilege policy for Jarvis Core operations
resource "aws_iam_policy" "jarvis_core_policy" {
  name        = "${var.environment}-jarvis-core-policy"
  description = "Policy granting Jarvis Core access to EventBridge, DynamoDB, and SQS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = var.event_bus_arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.events_queue_arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          var.world_model_table_arn,
          var.action_audit_table_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "jarvis_core_attach" {
  role       = aws_iam_role.jarvis_core_role.name
  policy_arn = aws_iam_policy.jarvis_core_policy.arn
}
