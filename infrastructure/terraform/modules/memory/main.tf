terraform {
  required_version = ">= 1.5.0"
}

# World Model State Table
resource "aws_dynamodb_table" "world_model" {
  name         = "${var.environment}-jarvis-world-model"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "entity_id"
  range_key    = "timestamp"

  attribute {
    name = "entity_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.environment}-jarvis-world-model"
    Project     = "JARVIS"
    Environment = var.environment
  }
}

# Action Audit & History Table
resource "aws_dynamodb_table" "action_audit" {
  name         = "${var.environment}-jarvis-action-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "action_id"
  range_key    = "timestamp"

  attribute {
    name = "action_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  tags = {
    Name        = "${var.environment}-jarvis-action-audit"
    Project     = "JARVIS"
    Environment = var.environment
  }
}

# S3 Bucket for Artifacts & Audio/Vision Snapshots
resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.environment}-jarvis-artifacts-${var.aws_account_id}"

  tags = {
    Name        = "${var.environment}-jarvis-artifacts"
    Project     = "JARVIS"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "artifacts_versioning" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts_encryption" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
