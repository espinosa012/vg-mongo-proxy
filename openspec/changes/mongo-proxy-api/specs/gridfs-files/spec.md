# Spec Delta: gridfs-files

## Purpose

Enables multipart file uploads, streaming file downloads, and file deletion in MongoDB using GridFS buckets to store task attachments without document size restrictions.

## ADDED Requirements

### Requirement: Upload Files to GridFS
The proxy API SHALL accept multipart/form-data file uploads and stream the file contents into MongoDB GridFS, returning metadata and the generated file ID.

#### Scenario: Successful file upload
- **WHEN** client sends a POST request to `/files/upload` with a multipart form payload containing a file
- **THEN** system streams the file to GridFS and returns HTTP 201 with the generated `file_id`, filename, content type, and file length in bytes

#### Scenario: Upload without file payload
- **WHEN** client sends a POST request to `/files/upload` without a file field
- **THEN** system returns HTTP 400 Bad Request indicating a missing file

### Requirement: Download and Stream Files from GridFS
The proxy API SHALL stream stored GridFS files by their ID directly to the HTTP client with appropriate media type headers.

#### Scenario: Stream existing file
- **WHEN** client sends a GET request to `/files/{file_id}` for an existing file
- **THEN** system streams the file content with HTTP 200 and sets `Content-Type` matching the stored MIME type

#### Scenario: Request non-existent file
- **WHEN** client sends a GET request to `/files/{file_id}` for a missing or invalid file ID
- **THEN** system returns HTTP 404 Not Found

### Requirement: Delete Files from GridFS
The proxy API SHALL allow removing a file and its constituent chunks from GridFS by file ID.

#### Scenario: Delete existing file
- **WHEN** client sends a DELETE request to `/files/{file_id}` for an existing file
- **THEN** system removes the file and chunks and returns HTTP 200 confirming deletion
