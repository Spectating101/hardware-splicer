import tempfile
import runpy
import os
from pathlib import Path

def script_to_stl(py_code: str, out_path: Path) -> None:
    """Execute generated CadQuery code and export STL."""
    temp_file = _write_temp(py_code)
    try:
        try:
            ns = runpy.run_path(temp_file)  # returns namespace with `result`
        except Exception as e:
            # Print generated code for debugging
            print(f"Generated code execution failed: {e}")
            print(f"Generated code at: {temp_file}")
            with open(temp_file) as f:
                print(f.read())
            raise
        assembly = ns.get("result")
        if assembly is None:
            # Print generated code for debugging
            print(f"result variable not set. Namespace keys: {list(ns.keys())}")
            print(f"Generated code at: {temp_file}")
            with open(temp_file) as f:
                print(f.read())
            raise RuntimeError("CadQuery script didn't set `result`")
        assembly.val().exportStl(str(out_path))
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def _write_temp(code: str) -> str:
    """Write code to temporary file and return path."""
    fd = tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w")
    try:
        fd.write(code)
        fd.flush()
        return fd.name
    finally:
        fd.close()
