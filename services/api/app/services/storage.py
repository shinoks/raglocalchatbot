import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status


@dataclass(slots=True)
class StoredUpload:
    checksum: str
    path: Path
    size: int
    format: str
    original_filename: str


class StorageService:
    def __init__(self, upload_dir: Path) -> None:
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile, max_bytes: int) -> StoredUpload:
        original_name = upload.filename or "document"
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".pdf", ".docx", ".doc", ".txt"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nieobsługiwany typ pliku.")

        filename = f"{uuid.uuid4()}{suffix}"
        destination = self.upload_dir / filename
        digest = hashlib.sha256()
        size = 0

        with destination.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    handle.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Plik przekracza maksymalny dozwolony rozmiar.",
                    )
                digest.update(chunk)
                handle.write(chunk)

        await upload.close()
        return StoredUpload(
            checksum=digest.hexdigest(),
            path=destination,
            size=size,
            format=suffix.lstrip("."),
            original_filename=original_name,
        )

    def delete(self, path: str | Path) -> None:
        os.unlink(path)

