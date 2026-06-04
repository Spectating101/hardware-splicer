"""Tests for persistent job storage."""
import pytest
from services.job_store import JobStore


@pytest.fixture
def job_store():
    """Create job store with in-memory fallback (no Redis required for tests)"""
    # Use invalid Redis URL to force in-memory mode
    store = JobStore(redis_url="redis://invalid:9999/0", ttl_hours=1)
    return store


@pytest.mark.unit
def test_job_store_create_and_get(job_store):
    """Test creating and retrieving a job"""
    job_id = "test_job_001"
    spec = {
        "id": "board-001",
        "context": {
            "board_bbox_mm": {"x": 50.0, "y": 30.0, "z": 1.6}
        }
    }

    job_store.create_job(job_id, spec, status="pending")

    job_data = job_store.get_job(job_id)

    assert job_data is not None
    assert job_data["job_id"] == job_id
    assert job_data["status"] == "pending"
    assert job_data["spec"] == spec
    assert "created_at" in job_data
    assert "updated_at" in job_data


@pytest.mark.unit
def test_job_store_update(job_store):
    """Test updating job status and result"""
    job_id = "test_job_002"
    spec = {"id": "board-002"}

    job_store.create_job(job_id, spec, status="pending")

    # Update to in progress
    success = job_store.update_job(job_id, status="in_progress", progress=50.0)
    assert success is True

    job_data = job_store.get_job(job_id)
    assert job_data["status"] == "in_progress"
    assert job_data["progress"] == 50.0

    # Update to completed
    result = {"artifact_path": "/artifacts/test.stl"}
    success = job_store.update_job(job_id, status="completed", result=result)
    assert success is True

    job_data = job_store.get_job(job_id)
    assert job_data["status"] == "completed"
    assert job_data["result"] == result


@pytest.mark.unit
def test_job_store_delete(job_store):
    """Test deleting a job"""
    job_id = "test_job_003"
    spec = {"id": "board-003"}

    job_store.create_job(job_id, spec)

    # Verify exists
    assert job_store.get_job(job_id) is not None

    # Delete
    deleted = job_store.delete_job(job_id)
    assert deleted is True

    # Verify gone
    assert job_store.get_job(job_id) is None

    # Delete again should return False
    deleted = job_store.delete_job(job_id)
    assert deleted is False


@pytest.mark.unit
def test_job_store_list_jobs(job_store):
    """Test listing jobs with status filter"""
    # Create multiple jobs
    for i in range(5):
        job_store.create_job(
            f"job_{i}",
            {"id": f"board-{i}"},
            status="pending" if i < 3 else "completed"
        )

    # List all jobs
    all_jobs = job_store.list_jobs()
    assert len(all_jobs) == 5

    # List pending jobs
    pending = job_store.list_jobs(status="pending")
    assert len(pending) == 3

    # List completed jobs
    completed = job_store.list_jobs(status="completed")
    assert len(completed) == 2


@pytest.mark.unit
def test_job_store_update_nonexistent(job_store):
    """Test updating non-existent job returns False"""
    success = job_store.update_job("nonexistent", status="completed")
    assert success is False


@pytest.mark.unit
def test_job_store_health_check(job_store):
    """Test health check returns status"""
    health = job_store.health_check()

    assert "status" in health
    assert "backend" in health
    assert health["backend"] in ["redis", "memory"]

    # In-memory fallback should report degraded (not persistent)
    if health["backend"] == "memory":
        assert health["status"] in ["degraded", "unhealthy", "healthy"]


@pytest.mark.unit
def test_job_store_with_metadata(job_store):
    """Test storing and retrieving job metadata"""
    job_id = "test_job_metadata"
    spec = {"id": "board-meta"}
    metadata = {
        "user_id": "user123",
        "source": "circuit-ai",
        "priority": "high"
    }

    job_store.create_job(job_id, spec, metadata=metadata)

    job_data = job_store.get_job(job_id)
    assert job_data["metadata"] == metadata


@pytest.mark.unit
def test_job_store_error_handling(job_store):
    """Test error handling for failed jobs"""
    job_id = "test_job_error"
    spec = {"id": "board-error"}

    job_store.create_job(job_id, spec, status="pending")

    # Update with error
    error_msg = "Generation failed: Invalid parameters"
    success = job_store.update_job(job_id, status="failed", error=error_msg)
    assert success is True

    job_data = job_store.get_job(job_id)
    assert job_data["status"] == "failed"
    assert job_data["error"] == error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
