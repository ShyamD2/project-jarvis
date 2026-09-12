terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      ec2        = var.localstack_endpoint
      events     = var.localstack_endpoint
      sqs        = var.localstack_endpoint
      dynamodb   = var.localstack_endpoint
      s3         = var.localstack_endpoint
      iam        = var.localstack_endpoint
      cloudwatch = var.localstack_endpoint
    }
  }
}

# 1. Networking Module
module "networking" {
  source      = "../../modules/networking"
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
}

# 2. Events Module (EventBridge & SQS)
module "events" {
  source         = "../../modules/events"
  environment    = var.environment
  event_bus_name = "${var.environment}-jarvis-bus"
}

# 3. Memory & Storage Module (DynamoDB & S3)
module "memory" {
  source         = "../../modules/memory"
  environment    = var.environment
  aws_account_id = var.aws_account_id
}

# 4. IAM Module
module "iam" {
  source                 = "../../modules/iam"
  environment            = var.environment
  event_bus_arn          = module.events.event_bus_arn
  events_queue_arn       = module.events.events_queue_arn
  world_model_table_arn  = module.memory.world_model_table_arn
  action_audit_table_arn = module.memory.action_audit_table_arn
}
