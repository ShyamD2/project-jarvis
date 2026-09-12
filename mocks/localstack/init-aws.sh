#!/bin/bash
echo "=== Initializing LocalStack AWS Resources for J.A.R.V.I.S. ==="

# Create EventBridge Bus
awslocal events create-event-bus --name jarvis-event-bus

# Create Dead Letter Queue & Processing Queues
awslocal sqs create-queue --queue-name jarvis-dlq
awslocal sqs create-queue --queue-name jarvis-events-queue

# Create State & Memory DynamoDB Tables
awslocal dynamodb create-table \
    --table-name jarvis_world_model \
    --attribute-definitions AttributeName=entity_id,AttributeType=S AttributeName=timestamp,AttributeType=N \
    --key-schema AttributeName=entity_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

awslocal dynamodb create-table \
    --table-name jarvis_action_audit \
    --attribute-definitions AttributeName=action_id,AttributeType=S AttributeName=timestamp,AttributeType=N \
    --key-schema AttributeName=action_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

awslocal dynamodb create-table \
    --table-name jarvis_locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# Create Artifacts S3 Bucket
awslocal s3 mb s3://jarvis-artifacts-local

echo "=== LocalStack AWS Resources Successfully Initialized ==="
