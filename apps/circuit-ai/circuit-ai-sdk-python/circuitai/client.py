"""
Circuit.AI Python SDK Client

Main client class for interacting with the Circuit.AI API.
"""

import requests
import base64
from typing import Optional, List, Dict, Any, Union, BinaryIO
from pathlib import Path
import json
from datetime import datetime

from .models import (
    Component,
    AnalysisResult,
    ProjectTemplate,
    EducationalContent,
    UsageStats,
    CircuitAIError,
    RateLimitError,
    AuthenticationError,
    APIError
)
from .exceptions import handle_api_error


class Client:
    """
    Circuit.AI API client for Python.
    
    This client provides a simple interface for interacting with the Circuit.AI
    PCB analysis API, including component detection, value assessment, and
    educational content retrieval.
    
    Example:
        ```python
        import circuitai
        
        client = circuitai.Client(api_key="your-api-key")
        
        # Analyze a PCB image
        result = client.analyze_pcb("path/to/pcb_image.jpg")
        
        print(f"Found {len(result.components)} components")
        for component in result.components:
            print(f"- {component.name}: ${component.value}")
        ```
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.circuit-ai.com",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize the Circuit.AI client.
        
        Args:
            api_key: Your Circuit.AI API key
            base_url: Base URL for the API (default: production)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"circuit-ai-python-sdk/1.0.0",
            "Content-Type": "application/json"
        })
    
    def analyze_pcb(
        self,
        image: Union[str, Path, BinaryIO],
        backend: Optional[str] = None,
        enable_ocr: bool = False
    ) -> AnalysisResult:
        """
        Analyze a PCB image for component detection and value assessment.
        
        Args:
            image: Path to image file, file-like object, or base64 string
            backend: Detection backend ("yolo" or "enhanced")
            enable_ocr: Enable OCR text extraction
            
        Returns:
            AnalysisResult containing detected components and analysis data
            
        Raises:
            CircuitAIError: If the analysis fails
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded
        """
        try:
            # Prepare image data
            if isinstance(image, (str, Path)):
                image_path = Path(image)
                if not image_path.exists():
                    raise FileNotFoundError(f"Image file not found: {image_path}")
                
                with open(image_path, "rb") as f:
                    image_data = f.read()
            elif hasattr(image, "read"):
                image_data = image.read()
            else:
                # Assume it's base64 encoded
                image_data = base64.b64decode(image)
            
            # Prepare form data
            files = {"file": ("image.jpg", image_data, "image/jpeg")}
            data = {}
            
            if backend:
                data["backend"] = backend
            if enable_ocr:
                data["enable_ocr"] = "true"
            
            # Make request
            response = self._make_request(
                "POST",
                "/v1/analyze",
                files=files,
                data=data
            )
            
            return AnalysisResult.from_dict(response)
            
        except Exception as e:
            if isinstance(e, (CircuitAIError, AuthenticationError, RateLimitError)):
                raise
            raise CircuitAIError(f"Failed to analyze PCB: {str(e)}")
    
    def analyze_pcb_batch(
        self,
        images: List[Union[str, Path, BinaryIO]],
        backend: Optional[str] = None,
        enable_ocr: bool = False
    ) -> List[AnalysisResult]:
        """
        Analyze multiple PCB images in a single request.
        
        Args:
            images: List of image paths, file-like objects, or base64 strings
            backend: Detection backend ("yolo" or "enhanced")
            enable_ocr: Enable OCR text extraction
            
        Returns:
            List of AnalysisResult objects
            
        Raises:
            CircuitAIError: If the batch analysis fails
        """
        try:
            batch_items = []
            
            for i, image in enumerate(images):
                # Prepare image data
                if isinstance(image, (str, Path)):
                    image_path = Path(image)
                    if not image_path.exists():
                        raise FileNotFoundError(f"Image file not found: {image_path}")
                    
                    with open(image_path, "rb") as f:
                        image_data = f.read()
                elif hasattr(image, "read"):
                    image_data = image.read()
                else:
                    # Assume it's base64 encoded
                    image_data = base64.b64decode(image)
                
                # Encode as base64
                image_b64 = base64.b64encode(image_data).decode("utf-8")
                
                batch_items.append({
                    "filename": f"image_{i}.jpg",
                    "content_base64": image_b64,
                    "backend": backend,
                    "enable_ocr": enable_ocr
                })
            
            # Make request
            response = self._make_request(
                "POST",
                "/v1/analyze/batch",
                json={"images": batch_items}
            )
            
            results = []
            for item in response.get("results", []):
                if item.get("success"):
                    results.append(AnalysisResult.from_dict(item))
                else:
                    # Create error result
                    error_result = AnalysisResult(
                        success=False,
                        analysis_id=None,
                        components=[],
                        total_value=0.0,
                        analysis_time=0.0,
                        timestamp=item.get("timestamp", ""),
                        error=item.get("error")
                    )
                    results.append(error_result)
            
            return results
            
        except Exception as e:
            if isinstance(e, (CircuitAIError, AuthenticationError, RateLimitError)):
                raise
            raise CircuitAIError(f"Failed to analyze PCB batch: {str(e)}")
    
    def get_components(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Component]:
        """
        Get information about supported electronic components.
        
        Args:
            search: Search term for component names
            category: Filter by component category
            limit: Maximum number of components to return
            offset: Number of components to skip
            
        Returns:
            List of Component objects
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if search:
            params["search"] = search
        if category:
            params["category"] = category
        
        response = self._make_request("GET", "/v1/components", params=params)
        
        components = []
        for comp_data in response.get("data", {}).get("components", []):
            components.append(Component.from_dict(comp_data))
        
        return components
    
    def get_projects(
        self,
        difficulty: Optional[str] = None,
        components: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[ProjectTemplate]:
        """
        Get educational project templates and recommendations.
        
        Args:
            difficulty: Filter by difficulty level ("beginner", "intermediate", "advanced")
            components: Filter by required components
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            
        Returns:
            List of ProjectTemplate objects
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if difficulty:
            params["difficulty"] = difficulty
        if components:
            params["components"] = ",".join(components)
        
        response = self._make_request("GET", "/v1/projects", params=params)
        
        projects = []
        for proj_data in response.get("data", {}).get("projects", []):
            projects.append(ProjectTemplate.from_dict(proj_data))
        
        return projects
    
    def get_educational_content(self, component_id: str) -> EducationalContent:
        """
        Get educational content and tutorials for a specific component.
        
        Args:
            component_id: Component identifier
            
        Returns:
            EducationalContent object
        """
        response = self._make_request("GET", f"/v1/educational/{component_id}")
        
        return EducationalContent.from_dict(response["data"])
    
    def get_analysis_history(
        self,
        limit: int = 20,
        offset: int = 0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[AnalysisResult]:
        """
        Get user's analysis history.
        
        Args:
            limit: Maximum number of analyses to return
            offset: Number of analyses to skip
            date_from: Start date filter (ISO format)
            date_to: End date filter (ISO format)
            
        Returns:
            List of AnalysisResult objects
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        
        response = self._make_request("GET", "/v1/analyses", params=params)
        
        analyses = []
        for analysis_data in response.get("data", {}).get("analyses", []):
            analyses.append(AnalysisResult.from_dict(analysis_data))
        
        return analyses
    
    def get_analysis(self, analysis_id: str) -> AnalysisResult:
        """
        Get a specific analysis by ID.
        
        Args:
            analysis_id: Analysis identifier
            
        Returns:
            AnalysisResult object
        """
        response = self._make_request("GET", f"/v1/analyses/{analysis_id}")
        
        return AnalysisResult.from_dict(response["data"])
    
    def export_analysis_csv(self, analysis_id: str) -> str:
        """
        Export analysis results as CSV.
        
        Args:
            analysis_id: Analysis identifier
            
        Returns:
            CSV content as string
        """
        response = self._make_request(
            "GET",
            f"/v1/analyses/{analysis_id}/export.csv",
            stream=True
        )
        
        return response.text
    
    def get_usage_stats(self) -> UsageStats:
        """
        Get API usage statistics for the current user.
        
        Returns:
            UsageStats object
        """
        response = self._make_request("GET", "/v1/usage")
        
        return UsageStats.from_dict(response["data"])
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status.
        
        Returns:
            Health status information
        """
        response = self._make_request("GET", "/v1/health")
        return response
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        stream: bool = False
    ) -> Union[Dict, requests.Response]:
        """
        Make an HTTP request to the API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json: JSON payload
            data: Form data
            files: File uploads
            stream: Whether to stream the response
            
        Returns:
            Response data or response object
        """
        url = f"{self.base_url}{endpoint}"
        
        # Remove Content-Type header for file uploads
        headers = self.session.headers.copy()
        if files:
            headers.pop("Content-Type", None)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=headers,
                    timeout=self.timeout,
                    stream=stream
                )
                
                # Handle different response types
                if stream:
                    return response
                
                # Check for errors
                if response.status_code >= 400:
                    handle_api_error(response)
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    raise CircuitAIError(f"Request failed after {self.max_retries} retries: {str(e)}")
                
                # Wait before retry
                import time
                time.sleep(2 ** attempt)
        
        raise CircuitAIError("Request failed after all retries")
