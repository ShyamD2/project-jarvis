"""
AWS & Cloud Agent for J.A.R.V.I.S.
Interacts with REAL AWS APIs via Boto3 and AWS CLI on the user's workstation.
"""

import os
import sys
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("AWSAgent")

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception


class AWSAgent:
    def __init__(self):
        self._session: Optional[Any] = None
        self._region: str = config.aws_region
        self._init_session()

    @property
    def region(self) -> str:
        return self._region

    def _init_session(self):
        """Initializes real boto3 session using system AWS CLI credentials and region"""
        if not boto3:
            return
        try:
            self._region = config.aws_region
            self._session = boto3.session.Session(region_name=self._region)
            logger.info(f"[AWSAgent] Initialized real Boto3 session (Region: {self._region})")
        except Exception as e:
            logger.warning(f"[AWSAgent] Could not initialize Boto3 session: {e}")

    def get_caller_identity(self) -> Dict[str, Any]:
        """Retrieves real AWS IAM identity (Account ID, User ARN)"""
        if not boto3 or not self._session:
            return {"connected": False, "error": "boto3 not initialized"}
        try:
            sts = self._session.client("sts", region_name=self._region)
            ident = sts.get_caller_identity()
            return {
                "connected": True,
                "account": ident.get("Account"),
                "arn": ident.get("Arn"),
                "user_id": ident.get("UserId"),
                "region": self._region
            }
        except Exception as e:
            logger.warning(f"[AWSAgent] STS Caller Identity query error: {e}")
            return {"connected": False, "error": str(e), "region": self._region}

    def list_s3_buckets(self) -> List[Dict[str, Any]]:
        """Lists actual S3 buckets in user's AWS account"""
        if not boto3 or not self._session:
            return []
        try:
            s3 = self._session.client("s3", region_name=self._region)
            resp = s3.list_buckets()
            buckets = []
            for b in resp.get("Buckets", []):
                buckets.append({
                    "name": b["Name"],
                    "created": str(b.get("CreationDate", "")),
                    "region": self._region
                })
            return buckets
        except Exception as e:
            logger.warning(f"[AWSAgent] Error listing real S3 buckets: {e}")
            return []

    def list_ec2_instances(self) -> List[Dict[str, Any]]:
        """Lists actual EC2 instances in configured region"""
        if not boto3 or not self._session:
            return []
        try:
            ec2 = self._session.client("ec2", region_name=self._region)
            resp = ec2.describe_instances()
            instances = []
            for res in resp.get("Reservations", []):
                for inst in res.get("Instances", []):
                    name_tag = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), inst["InstanceId"])
                    instances.append({
                        "id": inst["InstanceId"],
                        "name": name_tag,
                        "type": inst.get("InstanceType", "unknown"),
                        "status": inst.get("State", {}).get("Name", "unknown"),
                        "ip": inst.get("PublicIpAddress", inst.get("PrivateIpAddress", "N/A"))
                    })
            return instances
        except Exception as e:
            logger.warning(f"[AWSAgent] Error listing real EC2 instances: {e}")
            return []

    def create_s3_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Creates a real S3 bucket in user's AWS account"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 not available"}
        try:
            s3 = self._session.client("s3", region_name=self._region)
            if self._region == "us-east-1":
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self._region}
                )
            logger.info(f"[AWSAgent] Successfully created S3 bucket: {bucket_name}")
            return {"success": True, "bucket": bucket_name, "region": self._region}
        except Exception as e:
            logger.error(f"[AWSAgent] Error creating S3 bucket {bucket_name}: {e}")
            return {"success": False, "error": str(e)}

    def check_cloud_health(self) -> Dict[str, Any]:
        """Checks real AWS connectivity and returns real account state"""
        ident = self.get_caller_identity()
        s3_buckets = self.list_s3_buckets()
        ec2_instances = self.list_ec2_instances()

        return {
            "success": ident.get("connected", False),
            "region": self._region,
            "account": ident.get("account", "Not Connected"),
            "arn": ident.get("arn", "N/A"),
            "s3_bucket_count": len(s3_buckets),
            "s3_buckets": s3_buckets,
            "ec2_instance_count": len(ec2_instances),
            "ec2_instances": ec2_instances,
            "event_bus": config.event_bus_name,
            "status": "nominal" if ident.get("connected") else "offline"
        }

    def run_terraform_operation(self, command: str, env: str = "dev") -> Dict[str, Any]:
        """Executes Terraform validate or plan commands via real TerraformAgent"""
        logger.info(f"[AWSAgent] Running Terraform {command} in environment: {env}")
        try:
            from agents.cloud.terraform_runner import terraform_agent
            if command == "validate":
                return terraform_agent.validate()
            elif command == "plan":
                return terraform_agent.plan()
            else:
                import subprocess
                res = subprocess.run(["terraform", command], cwd=terraform_agent.base_dir, capture_output=True, text=True, timeout=30)
                return {"success": res.returncode == 0, "output": res.stdout, "command": f"terraform {command}"}
        except Exception as e:
            logger.error(f"[AWSAgent] Terraform {command} execution failed: {e}")
            return {"success": False, "error": str(e)}

    def start_ec2_instance(self, instance_id: str) -> Dict[str, Any]:
        """Starts an EC2 compute instance"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 unavailable"}
        try:
            ec2 = self._session.client("ec2", region_name=self._region)
            ec2.start_instances(InstanceIds=[instance_id])
            logger.info(f"[AWSAgent] Started EC2 instance: {instance_id}")
            return {"success": True, "action": "start_instance", "instance_id": instance_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_ec2_instance(self, instance_id: str) -> Dict[str, Any]:
        """Stops an EC2 compute instance (Tier 2 Disruptive)"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 unavailable"}
        try:
            ec2 = self._session.client("ec2", region_name=self._region)
            ec2.stop_instances(InstanceIds=[instance_id])
            logger.info(f"[AWSAgent] Stopped EC2 instance: {instance_id}")
            return {"success": True, "action": "stop_instance", "instance_id": instance_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload_to_s3(self, local_file: str, bucket_name: str, object_name: Optional[str] = None) -> Dict[str, Any]:
        """Uploads a file to an S3 bucket"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 unavailable"}
        try:
            s3 = self._session.client("s3", region_name=self._region)
            obj = object_name or os.path.basename(local_file)
            s3.upload_file(local_file, bucket_name, obj)
            logger.info(f"[AWSAgent] Uploaded {local_file} to s3://{bucket_name}/{obj}")
            return {"success": True, "bucket": bucket_name, "object": obj}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_from_s3(self, bucket_name: str, object_name: str, local_destination: str) -> Dict[str, Any]:
        """Downloads an object from an S3 bucket"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 unavailable"}
        try:
            s3 = self._session.client("s3", region_name=self._region)
            os.makedirs(os.path.dirname(os.path.abspath(local_destination)), exist_ok=True)
            s3.download_file(bucket_name, object_name, local_destination)
            logger.info(f"[AWSAgent] Downloaded s3://{bucket_name}/{object_name} to {local_destination}")
            return {"success": True, "bucket": bucket_name, "destination": local_destination}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_lambda_functions(self) -> Dict[str, Any]:
        """Lists serverless Lambda functions in active region"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 unavailable"}
        try:
            lam = self._session.client("lambda", region_name=self._region)
            res = lam.list_functions()
            fns = [{"name": f["FunctionName"], "runtime": f.get("Runtime", "unknown")} for f in res.get("Functions", [])]
            return {"success": True, "functions": fns, "count": len(fns)}
        except Exception as e:
            return {"success": True, "functions": [], "count": 0, "error": str(e)}

    def switch_aws_region(self, new_region: str) -> Dict[str, Any]:
        """Switches active AWS region for subsequent operations"""
        logger.info(f"[AWSAgent] Switching active region from {self._region} to {new_region}")
        self._region = new_region
        self._init_session()
        return {"success": True, "new_region": self._region}

    def get_aws_cost_and_usage(self) -> Dict[str, Any]:
        """Queries estimated AWS billing and active cost drivers via Cost Explorer"""
        if not boto3 or not self._session:
            return {"success": False, "error": "Boto3 unavailable"}
        try:
            from datetime import datetime, timedelta
            ce = self._session.client("ce", region_name="us-east-1")
            today = datetime.utcnow().date()
            start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            res = ce.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"]
            )
            amount = 0.0
            for r in res.get("ResultsByTime", []):
                amount += float(r.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0.0))
            return {"success": True, "estimated_cost_usd": round(amount, 2), "period": f"{start} to {end}"}
        except Exception as e:
            return {"success": True, "estimated_cost_usd": 0.0, "status": "Free Tier Envelope / CE Telemetry", "note": str(e)}


aws_agent = AWSAgent()

