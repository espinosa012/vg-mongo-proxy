from __future__ import annotations

import mimetypes
import secrets
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from gridfs.errors import NoFile

from vg_mongo_proxy.auth import get_custom_mongo_uri, verify_api_key
from vg_mongo_proxy.config import get_settings
from vg_mongo_proxy.db import get_gridfs_bucket
from vg_mongo_proxy.utils.ejson import serialize_bson

router = APIRouter(
    prefix="/files",
    tags=["GridFS Files"],
)


async def verify_file_access(
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    api_key: Optional[str] = Query(None, alias="key"),
) -> str:
    """Verify access via either x-api-key header or key query param (for direct browser links/images)."""
    settings = get_settings()
    expected_key = settings.proxy_api_key
    provided_key = x_api_key or api_key

    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured.",
        )

    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return provided_key


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(..., description="The binary file to upload to GridFS"),
    database: Optional[str] = Form(None, description="Database name (uses DEFAULT_DATABASE if omitted)"),
    bucket: str = Form("fs", description="GridFS bucket name"),
    _auth: str = Depends(verify_api_key),
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Upload a file to MongoDB GridFS via streaming."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided for upload.",
        )

    content_type = file.content_type
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(file.filename)
        content_type = guessed_type or "application/octet-stream"

    gridfs_bucket = get_gridfs_bucket(database, custom_uri, bucket_name=bucket)
    metadata = {
        "contentType": content_type,
        "originalFilename": file.filename,
    }

    upload_stream = gridfs_bucket.open_upload_stream(
        filename=file.filename,
        metadata=metadata,
    )

    try:
        while True:
            chunk = await file.read(1024 * 128)  # 128 KB chunks
            if not chunk:
                break
            await upload_stream.write(chunk)
    finally:
        await upload_stream.close()

    return {
        "fileId": str(upload_stream._id),
        "filename": file.filename,
        "contentType": content_type,
        "length": upload_stream.length,
    }


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    database: Optional[str] = Query(None, description="Database name"),
    bucket: str = Query("fs", description="GridFS bucket name"),
    download: bool = Query(False, description="Set Content-Disposition to attachment instead of inline"),
    _auth: str = Depends(verify_file_access),
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Download or stream a file from GridFS with proper content headers."""
    try:
        oid = ObjectId(file_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file ObjectId: {file_id}",
        )

    gridfs_bucket = get_gridfs_bucket(database, custom_uri, bucket_name=bucket)

    try:
        grid_out = await gridfs_bucket.open_download_stream(oid)
    except NoFile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found with ID: {file_id}",
        )

    # Resolve content type
    meta = grid_out.metadata or {}
    content_type = meta.get("contentType")
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(grid_out.filename or "")
        content_type = guessed_type or "application/octet-stream"

    disposition_type = "attachment" if download else "inline"
    filename = grid_out.filename or "file"

    headers = {
        "Content-Disposition": f'{disposition_type}; filename="{filename}"',
        "Content-Length": str(grid_out.length),
    }

    async def file_iterator():
        while True:
            chunk = await grid_out.readchunk()
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=content_type,
        headers=headers,
    )


@router.get("/{file_id}/info")
async def get_file_info(
    file_id: str,
    database: Optional[str] = Query(None, description="Database name"),
    bucket: str = Query("fs", description="GridFS bucket name"),
    _auth: str = Depends(verify_api_key),
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Retrieve metadata about a stored file without downloading its content."""
    try:
        oid = ObjectId(file_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file ObjectId: {file_id}",
        )

    gridfs_bucket = get_gridfs_bucket(database, custom_uri, bucket_name=bucket)

    try:
        grid_out = await gridfs_bucket.open_download_stream(oid)
    except NoFile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found with ID: {file_id}",
        )

    return {
        "fileId": str(grid_out._id),
        "filename": grid_out.filename,
        "length": grid_out.length,
        "uploadDate": serialize_bson(grid_out.upload_date),
        "metadata": serialize_bson(grid_out.metadata),
    }


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    database: Optional[str] = Query(None, description="Database name"),
    bucket: str = Query("fs", description="GridFS bucket name"),
    _auth: str = Depends(verify_api_key),
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Delete a file and its chunks from GridFS."""
    try:
        oid = ObjectId(file_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file ObjectId: {file_id}",
        )

    gridfs_bucket = get_gridfs_bucket(database, custom_uri, bucket_name=bucket)
    try:
        await gridfs_bucket.delete(oid)
    except NoFile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found with ID: {file_id}",
        )

    return {"deleted": True, "fileId": file_id}
