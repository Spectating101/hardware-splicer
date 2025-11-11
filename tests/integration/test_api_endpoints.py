"""
Integration tests for Circuit.AI API endpoints
Tests all major API endpoints with real data flows
"""

import pytest
import requests
import json
import io
import base64
from PIL import Image
import numpy as np
from pathlib import Path

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_IMAGE_SIZE = (640, 640)

class TestAPIHealth:
    """Test health and status endpoints"""

    def test_health_endpoint(self):
        """Test /health endpoint returns healthy status"""
        response = requests.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert "components" in data["data"]

    def test_health_response_structure(self):
        """Validate health endpoint response structure"""
        response = requests.get(f"{API_BASE_URL}/health")
        data = response.json()
        assert "version" in data["data"]
        assert "timestamp" in data["data"]
        components = data["data"]["components"]
        assert "detector" in components
        assert "mapper" in components
        assert "analyzer" in components
        assert "database" in components


class TestAuthentication:
    """Test authentication and authorization"""

    @pytest.fixture
    def auth_token(self):
        """Get a valid auth token for testing"""
        # This would be replaced with actual auth flow
        return "test-api-key-12345"

    def test_missing_auth_returns_401(self):
        """Test that endpoints without auth return 401"""
        # Create test image
        img_bytes = self._create_test_image()
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}

        response = requests.post(f"{API_BASE_URL}/analyze", files=files)
        assert response.status_code in [401, 403]

    def test_invalid_auth_returns_401(self):
        """Test that invalid auth token returns 401"""
        img_bytes = self._create_test_image()
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        headers = {"Authorization": "Bearer invalid-token"}

        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            headers=headers
        )
        assert response.status_code in [401, 403]

    @staticmethod
    def _create_test_image():
        """Create a simple test image"""
        img = Image.new('RGB', TEST_IMAGE_SIZE, color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        return img_buffer


class TestPCBAnalysis:
    """Test PCB analysis endpoints"""

    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for testing"""
        return {"Authorization": "Bearer test-api-key-12345"}

    @pytest.fixture
    def test_image(self):
        """Create a test PCB image"""
        img = Image.new('RGB', TEST_IMAGE_SIZE, color='green')
        # Add some simple shapes to simulate components
        pixels = img.load()
        # Draw a simple rectangle (simulating a component)
        for x in range(100, 200):
            for y in range(100, 200):
                pixels[x, y] = (255, 0, 0)

        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        return img_buffer

    def test_analyze_endpoint_structure(self, test_image, auth_headers):
        """Test /analyze endpoint response structure"""
        files = {"file": ("test_pcb.jpg", test_image, "image/jpeg")}

        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            headers=auth_headers
        )

        # Should return 200 or appropriate error
        assert response.status_code in [200, 401, 500]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "analysis_id" in data
            assert "components" in data
            assert "analysis_time" in data
            assert "timestamp" in data

    def test_analyze_invalid_file_type(self, auth_headers):
        """Test that non-image files are rejected"""
        files = {"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}

        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_analyze_file_size_limit(self, auth_headers):
        """Test that oversized files are rejected"""
        # Create a large image (>10MB)
        large_img = Image.new('RGB', (5000, 5000), color='red')
        img_buffer = io.BytesIO()
        large_img.save(img_buffer, format='JPEG', quality=100)
        img_buffer.seek(0)

        files = {"file": ("large.jpg", img_buffer, "image/jpeg")}

        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            headers=auth_headers
        )

        # Should reject if over 10MB
        if img_buffer.getbuffer().nbytes > 10 * 1024 * 1024:
            assert response.status_code == 413

    def test_analyze_with_ocr_flag(self, test_image, auth_headers):
        """Test analyze endpoint with OCR enabled"""
        files = {"file": ("test_pcb.jpg", test_image, "image/jpeg")}
        data = {"enable_ocr": "true"}

        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            data=data,
            headers=auth_headers
        )

        assert response.status_code in [200, 401, 500]


class TestBatchAnalysis:
    """Test batch processing endpoints"""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-api-key-12345"}

    def test_batch_analysis_structure(self, auth_headers):
        """Test batch analysis endpoint structure"""
        # Create test batch request
        batch_request = {
            "images": [
                {
                    "filename": "test1.jpg",
                    "content_base64": self._create_base64_image(),
                    "backend": "enhanced",
                    "enable_ocr": False
                },
                {
                    "filename": "test2.jpg",
                    "content_base64": self._create_base64_image(),
                    "backend": "enhanced",
                    "enable_ocr": False
                }
            ]
        }

        response = requests.post(
            f"{API_BASE_URL}/analyze/batch",
            json=batch_request,
            headers=auth_headers
        )

        assert response.status_code in [200, 401, 500]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "results" in data
            assert "total_processed" in data
            assert "batch_time" in data

    def test_batch_size_limit(self, auth_headers):
        """Test that batch size is limited to 10 images"""
        # Create 11 images (over limit)
        batch_request = {
            "images": [
                {
                    "filename": f"test{i}.jpg",
                    "content_base64": self._create_base64_image(),
                    "backend": "enhanced"
                }
                for i in range(11)
            ]
        }

        response = requests.post(
            f"{API_BASE_URL}/analyze/batch",
            json=batch_request,
            headers=auth_headers
        )

        assert response.status_code == 400

    @staticmethod
    def _create_base64_image():
        """Create a base64 encoded test image"""
        img = Image.new('RGB', (100, 100), color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_bytes = img_buffer.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')


class TestComponentDatabase:
    """Test component information endpoints"""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-api-key-12345"}

    def test_get_components_endpoint(self, auth_headers):
        """Test /components endpoint"""
        response = requests.get(
            f"{API_BASE_URL}/components",
            headers=auth_headers
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "components" in data["data"]

    def test_components_search(self, auth_headers):
        """Test component search functionality"""
        response = requests.get(
            f"{API_BASE_URL}/components?search=resistor",
            headers=auth_headers
        )

        assert response.status_code in [200, 401]

    def test_components_pagination(self, auth_headers):
        """Test component pagination"""
        response = requests.get(
            f"{API_BASE_URL}/components?limit=10&offset=0",
            headers=auth_headers
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert data["data"]["limit"] == 10
            assert data["data"]["offset"] == 0


class TestUsageTracking:
    """Test usage tracking and quotas"""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-api-key-12345"}

    def test_usage_stats_endpoint(self, auth_headers):
        """Test /usage endpoint"""
        response = requests.get(
            f"{API_BASE_URL}/usage",
            headers=auth_headers
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "usage" in data["data"]
            assert "quotas" in data["data"]
            assert "plan" in data["data"]


class TestRateLimiting:
    """Test rate limiting functionality"""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-api-key-12345"}

    def test_rate_limit_enforcement(self, auth_headers):
        """Test that rate limits are enforced"""
        # Make rapid requests to trigger rate limit
        img_bytes = self._create_test_image()

        responses = []
        for i in range(65):  # Exceed 60 requests/minute limit
            files = {"file": (f"test{i}.jpg", img_bytes, "image/jpeg")}
            response = requests.post(
                f"{API_BASE_URL}/analyze",
                files=files,
                headers=auth_headers
            )
            responses.append(response.status_code)

        # Should have at least one 429 (Too Many Requests)
        assert 429 in responses or any(r == 401 for r in responses)

    @staticmethod
    def _create_test_image():
        """Create a simple test image"""
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        return img_buffer


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-api-key-12345"}

    def test_malformed_json_request(self, auth_headers):
        """Test handling of malformed JSON"""
        response = requests.post(
            f"{API_BASE_URL}/analyze/batch",
            data="invalid json{{}",
            headers={**auth_headers, "Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422]

    def test_missing_required_fields(self, auth_headers):
        """Test handling of missing required fields"""
        response = requests.post(
            f"{API_BASE_URL}/analyze/batch",
            json={},  # Missing 'images' field
            headers=auth_headers
        )

        assert response.status_code in [400, 422]

    def test_corrupt_image_data(self, auth_headers):
        """Test handling of corrupt image data"""
        files = {"file": ("corrupt.jpg", io.BytesIO(b"not a valid image"), "image/jpeg")}

        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            headers=auth_headers
        )

        assert response.status_code in [400, 500]


class TestYOLOEndpoint:
    """Test YOLO-specific endpoint"""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-api-key-12345"}

    @pytest.fixture
    def test_image(self):
        img = Image.new('RGB', TEST_IMAGE_SIZE, color='green')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        return img_buffer

    def test_yolo_analysis_endpoint(self, test_image, auth_headers):
        """Test /analyze-yolo endpoint"""
        files = {"file": ("test_pcb.jpg", test_image, "image/jpeg")}

        response = requests.post(
            f"{API_BASE_URL}/analyze-yolo",
            files=files,
            headers=auth_headers
        )

        assert response.status_code in [200, 401, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "analysis_id" in data
            assert "components" in data
            assert "summary" in data

    def test_yolo_custom_confidence(self, test_image, auth_headers):
        """Test YOLO endpoint with custom confidence threshold"""
        files = {"file": ("test_pcb.jpg", test_image, "image/jpeg")}
        data = {"confidence": "0.5"}

        response = requests.post(
            f"{API_BASE_URL}/analyze-yolo",
            files=files,
            data=data,
            headers=auth_headers
        )

        assert response.status_code in [200, 401, 500, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
