# Tasks: MongoDB Proxy API

## 1. Project Scaffolding and Environment

- [x] 1.1 Create `pyproject.toml` with PEP 621 metadata, dependencies (FastAPI, Uvicorn, Motor, PyMongo, Pydantic, python-multipart, pytest, httpx), and `.gitignore` excluding `.env`, `.venv`, and cache files.
- [x] 1.2 Initialize git repository, configure remote `https://github.com/espinosa012/vg-mongo-proxy`, and verify git status.
- [x] 1.3 Create configuration module with `pydantic-settings` to load `MONGODB_URI`, `DEFAULT_DATABASE`, `PROXY_API_KEY`, and `CORS_ORIGINS`, along with a `.env.example` template.

## 2. Core Connection, Security, and Health

- [x] 2.1 Implement MongoDB connection pool and client manager using `motor.motor_asyncio` within FastAPI `lifespan` handler.
- [x] 2.2 Implement `x-api-key` header verification dependency and dynamic CORS middleware configured from `CORS_ORIGINS`.
- [x] 2.3 Implement `/health` endpoint reporting service readiness and database connectivity ping.

## 3. Generic Data API (`/action/*`)

- [x] 3.1 Implement BSON Extended JSON (`ejson`) conversion utilities to parse and serialize `ObjectId`, dates, and BSON types cleanly.
- [x] 3.2 Implement read action endpoints: `POST /action/find`, `POST /action/findOne`, `POST /action/count`, and `POST /action/aggregate`.
- [x] 3.3 Implement mutation action endpoints: `POST /action/insertOne`, `POST /action/insertMany`, `POST /action/updateOne`, `POST /action/updateMany`, `POST /action/deleteOne`, and `POST /action/deleteMany`.
- [x] 3.4 Create automated test suite for Data API endpoints and verify passing tests.

## 4. GridFS File Storage (`/files/*`)

- [x] 4.1 Implement `POST /files/upload` handling multipart uploads and streaming directly into `AsyncIOMotorGridFSBucket`.
- [x] 4.2 Implement `GET /files/{file_id}` (streaming file content with correct Content-Type) and `DELETE /files/{file_id}`.
- [x] 4.3 Create automated test suite for GridFS file upload, download, and delete operations.

## 5. Deployment Setup, Documentation, and Repository Sync

- [x] 5.1 Create `render.yaml` configuration defining the Render Web Service build, start command, and environment variable requirements.
- [x] 5.2 Create detailed `README.md` explaining where and how the Atlas connection string secret is stored, how to deploy to Render, and how to connect from GitHub Pages.
- [x] 5.3 Commit all changes to git and push to the remote GitHub repository at `https://github.com/espinosa012/vg-mongo-proxy`.
