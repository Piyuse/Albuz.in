MAX_PHOTO_MIB = 300
MAX_PHOTO_BYTES = MAX_PHOTO_MIB * 1024 * 1024
MAX_PHOTO_PIXELS = 80_000_000
MAX_BULK_UPLOAD_BYTES = 10 * MAX_PHOTO_BYTES

PHOTO_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "MPO": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
