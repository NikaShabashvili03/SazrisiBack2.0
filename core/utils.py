import os
import uuid
from PIL import Image
from io import BytesIO
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.files import File

def image_upload(instance, filename, dir):
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join(dir, filename)

def validate_image(image_field, max_size_kb=1200, compress_quality=75, path=''):
    try:
        img = Image.open(image_field)
        img = img.convert('RGB')

        if img.width > 4000 or img.height > 4000:
            img.thumbnail((int(img.width / 2), int(img.height / 2)))

        buffer = BytesIO()
        img.save(buffer, format='WEBP', quality=compress_quality, optimize=True)
        buffer.seek(0)

        webp_filename = f"{uuid.uuid4()}.webp"
        file_path = os.path.join(settings.MEDIA_ROOT, path, webp_filename)

        print(f"Saving image at: {file_path}")
        with default_storage.open(file_path, 'wb') as f:
            f.write(buffer.read())

        return f"{path}{webp_filename}"

    except Exception as e:
        raise ValidationError(f"Image compression failed: {str(e)}")