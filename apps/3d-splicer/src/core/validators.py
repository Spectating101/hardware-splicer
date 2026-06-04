from typing import Dict, Any

try:
    import trimesh  # type: ignore
except Exception:
    trimesh = None


def validate_stl(path: str) -> Dict[str, Any]:
    """Validate STL file and return mesh properties."""
    try:
        if trimesh is None:
            raise RuntimeError("trimesh is not installed")
        mesh = trimesh.load_mesh(path, force='mesh')
        return {
            "watertight": mesh.is_watertight,
            "euler_number": mesh.euler_number,
            "faces": int(mesh.faces.shape[0]),
            "bounds": mesh.bounds.tolist(),
            "volume": float(mesh.volume) if hasattr(mesh, 'volume') else None,
            "is_valid": mesh.is_watertight and mesh.faces.shape[0] > 0
        }
    except Exception as e:
        return {
            "error": str(e),
            "is_valid": False,
            "watertight": False,
            "euler_number": None,
            "faces": 0,
            "bounds": None,
            "volume": None
        }
