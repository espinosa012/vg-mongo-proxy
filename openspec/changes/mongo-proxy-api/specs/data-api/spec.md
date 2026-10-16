# Spec Delta: data-api

## Purpose

Provides generic HTTP endpoints to execute MongoDB queries, insertions, updates, deletions, and aggregation pipelines using standard JSON and BSON Extended JSON formats.

## ADDED Requirements

### Requirement: Document Query Operations
The proxy API SHALL support `find` and `findOne` operations against any MongoDB collection with optional query filtering, projections, sorting, and pagination.

#### Scenario: Query multiple documents with filter and limit
- **WHEN** client sends a POST request to `/action/find` with a collection name, filter criteria, and limit
- **THEN** system returns HTTP 200 with an array of matching documents serialized as JSON with parsed ObjectIds and dates

#### Scenario: Query a single document
- **WHEN** client sends a POST request to `/action/findOne` with a collection name and filter
- **THEN** system returns HTTP 200 with the matching document or null if not found

### Requirement: Document Insertion Operations
The proxy API SHALL support `insertOne` and `insertMany` operations to persist new documents in MongoDB.

#### Scenario: Insert a single document
- **WHEN** client sends a POST request to `/action/insertOne` with a valid document payload
- **THEN** system returns HTTP 200 containing the inserted document ID (`insertedId`)

#### Scenario: Insert multiple documents
- **WHEN** client sends a POST request to `/action/insertMany` with an array of documents
- **THEN** system returns HTTP 200 containing an array of inserted document IDs (`insertedIds`)

### Requirement: Document Mutation Operations
The proxy API SHALL support `updateOne`, `updateMany`, `deleteOne`, and `deleteMany` operations with filter criteria and atomic update operators.

#### Scenario: Update matching document with operators
- **WHEN** client sends a POST request to `/action/updateOne` with a filter and `$set` update operators
- **THEN** system returns HTTP 200 containing `matchedCount` and `modifiedCount`

#### Scenario: Delete matching documents
- **WHEN** client sends a POST request to `/action/deleteOne` or `/action/deleteMany` with a filter
- **THEN** system returns HTTP 200 containing `deletedCount`

### Requirement: Aggregation Pipeline and Counting
The proxy API SHALL support aggregation pipelines and document count queries against any collection.

#### Scenario: Run aggregation pipeline
- **WHEN** client sends a POST request to `/action/aggregate` with a collection name and pipeline array
- **THEN** system returns HTTP 200 with the aggregation results array

#### Scenario: Count matching documents
- **WHEN** client sends a POST request to `/action/count` with a collection name and filter
- **THEN** system returns HTTP 200 with the integer count of matching documents
