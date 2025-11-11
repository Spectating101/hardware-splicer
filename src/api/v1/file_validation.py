"""
File Upload Validation Module

Provides comprehensive validation for uploaded files to prevent:
- Excessive file sizes (DoS prevention)
- Invalid image formats
- Corrupted files
- Malicious uploads
"""

import io
from typing import Tuple, Optional
from PIL import Image
from loguru import logger

# Try to import python-magic for MIME type detection (optional)
# Removed: can be added later if needed
# For now, PIL provides sufficient format detection





# Configuration
MAX_FILE_SIZE_MB = 50  # Maximum 50MB per file
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

MAX_IMAGE_DIMENSIONS = (65536, 65536)  # Maximum 65k x 65k pixels
MIN_IMAGE_DIMENSIONS = (64, 64)  # Minimum 64x64 pixels

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
    "image/bmp": [".bmp"],
    "image/tiff": [".tiff", ".tif"],
    "image/gif": [".gif"],  # Not ideal for ML, but allowed
}

# Allowed file extensions (lowercase)
ALLOWED_EXTENSIONS = set()
for ext_list in ALLOWED_MIME_TYPES.values():
    ALLOWED_EXTENSIONS.update(ext_list)

# Minimum file size (to catch invalid files)
MIN_FILE_SIZE_BYTES = 100  # At least 100 bytes


class FileValidationError(Exception):
    """Custom exception for file validation errors."""
    pass


def validate_file_size(file_size: int) -> Tuple[bool, Optional[str]]:
    """
    Validate file size.
    
    Args:
        file_size: File size in bytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if file_size <= 0:
        return False, "File size is zero or invalid"
    
    if file_size < MIN_FILE_SIZE_BYTES:
        return False, f"File is too small (minimum {MIN_FILE_SIZE_BYTES} bytes)"
    
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f"File is too large (maximum {MAX_FILE_SIZE_MB}MB)"
    
    return True, None


def validate_file_extension(filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate file extension.
    
    Args:
        filename: Original filename
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename or "." not in filename:
        return False, "Filename does not have an extension"
    
    ext = "." + filename.rsplit(".", 1)[1].lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    
    return True, None


def validate_image_format(file_content: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate image format and MIME type using PIL.
    
    Args:
        file_content: Raw file bytes
        
    Returns:
        Tuple of (is_valid, error_message, mime_type)
    """
    if not file_content:
        return False, "File content is empty", None
    
    # Try to open as image to verify it's actually valid
    try:
        img = Image.open(io.BytesIO(file_content))
        img.load()  # Force image load to verify it's not corrupted
        
        width, height = img.size
        image_format = img.format.lower() if img.format else "unknown"
        logger.debug(f"Image dimensions: {width}x{height}, format: {image_format}")
        
        # Check if format is allowed
        if image_format not in ["jpeg", "jpg", "png", "webp", "bmp", "tiff", "gif"]:
            return False, f"Image format '{image_format}' not allowed", image_format
        
        return True, None, image_format
    except Image.UnidentifiedImageError:
        return False, "File is not a valid image (cannot identify format)", None
    except Exception as e:
        return False, f"Image validation error: {str(e)}", None


def validate_image_dimensions(file_content: bytes) -> Tuple[bool, Optional[str], Optional[Tuple[int, int]]]:
    """
    Validate image dimensions.
    
    Args:
        file_content: Raw file bytes
        
    Returns:
        Tuple of (is_valid, error_message, (width, height))
    """
    try:
        img = Image.open(io.BytesIO(file_content))
        width, height = img.size
        
        # Check minimum dimensions
        if width < MIN_IMAGE_DIMENSIONS[0] or height < MIN_IMAGE_DIMENSIONS[1]:
            return False, f"Image too small (minimum {MIN_IMAGE_DIMENSIONS[0]}x{MIN_IMAGE_DIMENSIONS[1]})", (width, height)
        
        # Check maximum dimensions
        if width > MAX_IMAGE_DIMENSIONS[0] or height > MAX_IMAGE_DIMENSIONS[1]:
            return False, f"Image too large (maximum {MAX_IMAGE_DIMENSIONS[0]}x{MAX_IMAGE_DIMENSIONS[1]})", (width, height)
        
        return True, None, (width, height)
    except Exception as e:
        return False, f"Error checking image dimensions: {str(e)}", None


def validate_image_content(file_content: bytes) -> Tuple[bool, Optional[str], Optional[Image.Image]]:
    """
    Validate image content and attempt to correct EXIF rotation.
    
    Args:
        file_content: Raw file bytes
        
    Returns:
        Tuple of (is_valid, error_message, PIL_Image)
    """
    try:
        img = Image.open(io.BytesIO(file_content))
        
        # Handle EXIF rotation
        try:
            from PIL.Image import Exif
            exif = img.getexif()
            if exif and 274 in exif:  # 274 is EXIF Orientation tag
                orientation = exif[274]
                # Apply rotation if needed
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
                logger.debug(f"EXIF rotation applied: {orientation}")
        except Exception as e:
            logger.debug(f"Could not process EXIF data: {e}")
        
        # Verify it's a valid image by attempting to load all bands
        img.load()
        
        return True, None, img
    except Exception as e:
        return False, f"Error processing image content: {str(e)}", None


def validate_file_upload(
    filename: str,
    file_content: bytes,
    strict: bool = True
) -> dict:
    """
    Comprehensive file validation for uploaded PCB images.
    
    Performs all validation checks and returns detailed results.
    
    Args:
        filename: Original filename
        file_content: Raw file bytes
        strict: If True, fail on any warning; if False, only fail on errors
        
    Returns:
        Validation result dict with:
        - is_valid (bool): Overall validation result
        - errors (list): List of errors (validation failed)
        - warnings (list): List of warnings (validation succeeded but suspicious)
        - details (dict): Additional information (mime_type, dimensions, etc.)
        
    Raises:
        FileValidationError: If validation completely fails
    """
    errors = []
    warnings = []
    details = {
        "filename": filename,
        "file_size_mb": len(file_content) / (1024 * 1024),
        "mime_type": None,
        "image_format": None,
        "dimensions": None,
    }
    
    # 1. Validate file size
    is_valid, error = validate_file_size(len(file_content))
    if not is_valid:
        errors.append(error)
        raise FileValidationError(error)
    
    # 2. Validate file extension
    is_valid, error = validate_file_extension(filename)
    if not is_valid:
        errors.append(error)
        if strict:
            raise FileValidationError(error)
        else:
            warnings.append(error)
    
    # 3. Validate image format
    is_valid, error, mime_type = validate_image_format(file_content)
    details["mime_type"] = mime_type
    if not is_valid:
        errors.append(error)
        if strict:
            raise FileValidationError(error)
        else:
            warnings.append(error)
    
    # 4. Validate image dimensions
    is_valid, error, dimensions = validate_image_dimensions(file_content)
    if dimensions:
        details["dimensions"] = {"width": dimensions[0], "height": dimensions[1]}
    if not is_valid:
        errors.append(error)
        if strict:
            raise FileValidationError(error)
        else:
            warnings.append(error)
    
    # 5. Validate image content
    is_valid, error, img = validate_image_content(file_content)
    if not is_valid:
        errors.append(error)
        if strict:
            raise FileValidationError(error)
        else:
            warnings.append(error)
    else:
        if img:
            details["image_format"] = img.format
            details["color_mode"] = img.mode
    
    # Determine overall validity
    overall_valid = len(errors) == 0
    
    if not overall_valid and strict:
        raise FileValidationError(f"File validation failed: {'; '.join(errors)}")
    
    return {
        "is_valid": overall_valid,
        "errors": errors,
        "warnings": warnings,
        "details": details,
        "image": img if is_valid else None
    }


# FastAPI dependency for file validation
async def validate_upload_dependency(file_content: bytes, filename: str) -> dict:
    """
    FastAPI dependency for validating uploads.
    
    Usage in endpoint:
        validation_result = await validate_upload_dependency(file.file.read(), file.filename)
        if not validation_result["is_valid"]:
            raise HTTPException(status_code=400, detail=validation_result["errors"])
    """
    try:
        return validate_file_upload(filename, file_content, strict=False)
    except FileValidationError as e:
        logger.error(f"File validation failed: {e}")
        return {
            "is_valid": False,
            "errors": [str(e)],
            "warnings": [],
            "details": {}
        }
