# Spec Delta: auth-security

## Purpose

Enforces access control using an API key header, manages cross-origin resource sharing for web clients like GitHub Pages, and exposes service health checks.

## ADDED Requirements

### Requirement: API Key Authentication
The proxy API SHALL enforce that all protected endpoints require a valid API key passed via the `x-api-key` header matching the configured secret.

#### Scenario: Request with valid API key
- **WHEN** client sends a request to any `/action/*` or `/files/*` endpoint with a matching `x-api-key` header
- **THEN** system authorizes and processes the request

#### Scenario: Request with missing or invalid API key
- **WHEN** client sends a request with an invalid or absent `x-api-key` header
- **THEN** system rejects the request with HTTP 401 Unauthorized

### Requirement: Cross-Origin Resource Sharing
The proxy API SHALL handle CORS preflight OPTIONS requests and attach allowed origins according to the configured `CORS_ORIGINS` environment variable.

#### Scenario: Preflight request from allowed origin
- **WHEN** browser sends an OPTIONS preflight request from an origin listed in `CORS_ORIGINS` (such as GitHub Pages or localhost)
- **THEN** system returns HTTP 200 with appropriate `Access-Control-Allow-Origin` and allowed headers (`x-api-key`, `Content-Type`)

### Requirement: Health Check and Readiness
The proxy API SHALL provide an unauthenticated health check endpoint at `/health` to verify service responsiveness and MongoDB cluster connectivity.

#### Scenario: Healthy service and database connection
- **WHEN** client sends a GET request to `/health`
- **THEN** system pings the MongoDB instance and returns HTTP 200 with status ok and connection latency
