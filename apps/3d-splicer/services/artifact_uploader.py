"""
Artifact uploader for S3/MinIO cloud storage integration.
"""

import os
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ArtifactUploader:
    """Upload artifacts to cloud storage (S3/MinIO)"""
    
    def __init__(self, 
                 bucket_name: str,
                 endpoint_url: Optional[str] = None,
                 access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 region: str = "us-east-1"):
        """
        Initialize artifact uploader.
        
        Args:
            bucket_name: S3/MinIO bucket name
            endpoint_url: MinIO endpoint (None for AWS S3)
            access_key: Access key (from env if None)
            secret_key: Secret key (from env if None)
            region: AWS region (ignored for MinIO)
        """
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region = region
        
        # Get credentials from environment if not provided
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        
        # Initialize boto3 client
        self._init_client()
    
    def _init_client(self):
        """Initialize boto3 S3 client"""
        try:
            import boto3
            from botocore.config import Config
            
            config = Config(region_name=self.region)
            
            if self.endpoint_url:
                # MinIO configuration
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    config=config
                )
                logger.info(f"Initialized MinIO client for bucket: {self.bucket_name}")
            else:
                # AWS S3 configuration
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    config=config
                )
                logger.info(f"Initialized S3 client for bucket: {self.bucket_name}")
                
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def upload_artifacts(self, job_id: str, artifacts: Dict[str, str]) -> Dict[str, str]:
        """
        Upload artifacts to cloud storage.
        
        Args:
            job_id: Job identifier
            artifacts: Dictionary of artifact_type -> local_path
            
        Returns:
            Dictionary of artifact_type -> cloud_url
        """
        cloud_artifacts = {}
        
        for artifact_type, local_path in artifacts.items():
            try:
                # Generate cloud path
                cloud_path = f"jobs/{job_id}/{artifact_type}"
                
                # Determine content type
                content_type = self._get_content_type(artifact_type)
                
                # Upload file
                self.s3_client.upload_file(
                    local_path,
                    self.bucket_name,
                    cloud_path,
                    ExtraArgs={'ContentType': content_type}
                )
                
                # Generate URL
                cloud_url = self._generate_url(cloud_path)
                cloud_artifacts[artifact_type] = cloud_url
                
                logger.info(f"Uploaded {artifact_type}: {local_path} → {cloud_url}")
                
            except Exception as e:
                logger.error(f"Failed to upload {artifact_type}: {e}")
                # Continue with other artifacts
                continue
        
        return cloud_artifacts
    
    def upload_job_artifacts(self, job_id: str, job_dir: Path) -> Dict[str, str]:
        """
        Upload all artifacts from job directory.
        
        Args:
            job_id: Job identifier
            job_dir: Local job directory path
            
        Returns:
            Dictionary of artifact_type -> cloud_url
        """
        artifacts = {}
        
        # Find STL files
        stl_files = list(job_dir.glob("*.stl"))
        if stl_files:
            artifacts["stl"] = str(stl_files[0])
        
        # Find GLB files
        glb_files = list(job_dir.glob("*.glb"))
        if glb_files:
            artifacts["glb"] = str(glb_files[0])
        
        # Find report files
        report_files = list(job_dir.glob("*_report.md"))
        if report_files:
            artifacts["report"] = str(report_files[0])
        
        # Find parameter files
        param_files = list(job_dir.glob("*_params.json"))
        if param_files:
            artifacts["parameters"] = str(param_files[0])
        
        return self.upload_artifacts(job_id, artifacts)
    
    def _get_content_type(self, artifact_type: str) -> str:
        """Get MIME content type for artifact"""
        content_types = {
            "stl": "application/octet-stream",
            "glb": "model/gltf-binary",
            "report": "text/markdown",
            "parameters": "application/json",
            "json": "application/json",
            "md": "text/markdown"
        }
        
        return content_types.get(artifact_type, "application/octet-stream")
    
    def _generate_url(self, cloud_path: str) -> str:
        """Generate public URL for uploaded artifact"""
        if self.endpoint_url:
            # MinIO URL
            return f"{self.endpoint_url}/{self.bucket_name}/{cloud_path}"
        else:
            # AWS S3 URL
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{cloud_path}"
    
    def test_connection(self) -> bool:
        """Test connection to cloud storage"""
        try:
            # Try to list bucket contents (limited to 1 item)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            logger.info("Cloud storage connection test: ✅ SUCCESS")
            return True
        except Exception as e:
            logger.error(f"Cloud storage connection test: ❌ FAILED - {e}")
            return False

# Convenience function for easy integration
def upload_job_to_cloud(job_id: str, 
                       job_dir: Path,
                       bucket_name: str = None,
                       endpoint_url: str = None) -> Dict[str, str]:
    """
    Convenience function to upload job artifacts to cloud storage.
    
    Args:
        job_id: Job identifier
        job_dir: Local job directory
        bucket_name: Override bucket name (defaults to env var)
        endpoint_url: Override endpoint (defaults to env var)
        
    Returns:
        Dictionary of artifact_type -> cloud_url
    """
    # Get configuration from environment
    bucket = bucket_name or os.getenv("ARTIFACT_BUCKET", "3d-splicer-artifacts")
    endpoint = endpoint_url or os.getenv("MINIO_ENDPOINT")
    
    uploader = ArtifactUploader(
        bucket_name=bucket,
        endpoint_url=endpoint
    )
    
    return uploader.upload_job_artifacts(job_id, job_dir)
