# Design: MongoDB Proxy API

## Context

Static web applications (such as a task manager hosted on GitHub Pages) cannot connect directly to MongoDB Atlas via TCP drivers without exposing credentials in client-side code. This design establishes a secure, lightweight HTTP proxy using Python 3.11+ and FastAPI deployed to Render, providing both generic Data API actions and GridFS file storage.

## Goals / Non-Goals

**Goals:**
- Provide generic Data API endpoints (`/action/*`) supporting standard MongoDB CRUD and aggregation pipelines.
- Provide file upload and streaming download endpoints (`/files/*`) backed by MongoDB GridFS.
- Support BSON/EJSON serialization for transparent `ObjectId` and `datetime` handling in JSON payloads.
- Manage database connections via a persistent connection pool using `motor.motor_asyncio`.
- Enforce API key authentication via `x-api-key` header and configurable CORS origins.
- Package the service with modern `pyproject.toml` (PEP 621) and configure deployment for Render.

**Non-Goals:**
- End-user authentication/session management (handled by client applications or dedicated identity providers).
- GraphQL or OData query layers.
- Direct database administration UI (users can inspect schemas via FastAPI `/docs` or MongoDB Atlas).

## Decisions

### 1. Framework: FastAPI + Motor (AsyncIOMotorClient)
- **Rationale**: FastAPI provides high performance, automatic OpenAPI documentation at `/docs`, native async support, and clean dependency injection. `motor` is the official async driver for MongoDB in Python, integrating directly with `asyncio`.
- **Alternatives considered**:
  - *Node.js + Fastify*: Fast and light, but lacks built-in interactive Swagger UI out of the box and requires TypeScript compilation steps.
  - *Django / Flask*: Heavier overhead, synchronous defaults, less suited for lightweight streaming proxies on Render free tier.

### 2. Dependency Management: `pyproject.toml` (PEP 621)
- **Rationale**: Follows standard modern Python packaging conventions. Render builds directly using `pip install .`.
- **Dependencies**: `fastapi`, `uvicorn[standard]`, `motor`, `pymongo`, `pydantic`, `pydantic-settings`, `python-multipart`.

### 3. File Handling: GridFS Streaming over Document Embedding
- **Rationale**: MongoDB documents have a 16 MB limit. Embedding files in documents as Base64 bloats payload sizes by ~33% and consumes high RAM. GridFS splits files into 255 KB chunks across `fs.files` and `fs.chunks`. Using FastAPI's `UploadFile` and `StreamingResponse` allows streaming directly to and from MongoDB without buffering complete files in memory.
- **Alternatives considered**:
  - *Base64 JSON in documents*: Simpler to implement but crashes with large attachments and risks hitting document size limits.

### 4. Serialization: BSON Extended JSON (`bson.json_util`)
- **Rationale**: MongoDB returns types like `ObjectId` and `datetime` which fail standard Python `json.dumps`. Using PyMongo's `bson.json_util.dumps` and `loads` ensures standard JSON compliance while preserving full BSON fidelity.

### 5. Secrets and Configuration Management
- **Rationale**: Secret credentials must never be committed to git.
  - Local environment: Loaded from `.env` using `pydantic-settings` (with `.env` added to `.gitignore`).
  - Production environment: Configured as Environment Secrets in Render's dashboard (`MONGODB_URI`, `PROXY_API_KEY`, `DEFAULT_DATABASE`, `CORS_ORIGINS`).

## Risks / Trade-offs

- **[Render Free Tier Sleep / Cold Starts]** → *Mitigation*: Provide an unauthenticated `GET /health` endpoint that the frontend can ping to wake up the service while showing a loading state to the user.
- **[Credential Exposure on GitHub Pages]** → *Mitigation*: The `MONGODB_URI` remains exclusively on Render. The frontend only holds a proxy API key and talks over HTTPS.
- **[Connection Exhaustion]** → *Mitigation*: Manage a single `AsyncIOMotorClient` instance throughout the application lifespan using FastAPI's `lifespan` context manager.
- **[Malicious Admin Commands]** → *Mitigation*: Limit proxy operations to collection-level CRUD and aggregation; disallow administrative commands (`dropDatabase`, `eval`, etc.).

## Migration / Deployment Plan

1. Initialize git repository in this directory.
2. Implement project structure (`src/`, `pyproject.toml`, tests).
3. Connect repository to GitHub: `https://github.com/espinosa012/vg-mongo-proxy`.
4. Configure Render Web Service:
   - Build command: `pip install .`
   - Start command: `uvicorn vg_mongo_proxy.main:app --host 0.0.0.0 --port $PORT`
   - Environment variables: `MONGODB_URI`, `PROXY_API_KEY`, `DEFAULT_DATABASE`, `CORS_ORIGINS`.
