from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from vg_mongo_proxy.auth import get_custom_mongo_uri, verify_api_key
from vg_mongo_proxy.db import get_database
from vg_mongo_proxy.utils.ejson import parse_ejson, serialize_bson

router = APIRouter(
    prefix="/action",
    tags=["Data API"],
    dependencies=[Depends(verify_api_key)],
)


class BaseActionRequest(BaseModel):
    database: Optional[str] = Field(None, description="Target database name (uses DEFAULT_DATABASE if omitted)")
    collection: str = Field(..., description="Target collection name")


class FindRequest(BaseActionRequest):
    filter: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query filter")
    projection: Optional[Dict[str, Any]] = Field(None, description="Projection document")
    sort: Optional[Dict[str, int]] = Field(None, description="Sort order, e.g. {'created_at': -1}")
    limit: Optional[int] = Field(100, ge=1, le=5000, description="Max documents to return")
    skip: Optional[int] = Field(0, ge=0, description="Documents to skip")


class FindOneRequest(BaseActionRequest):
    filter: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query filter")
    projection: Optional[Dict[str, Any]] = Field(None, description="Projection document")


class CountRequest(BaseActionRequest):
    filter: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query filter")


class AggregateRequest(BaseActionRequest):
    pipeline: List[Dict[str, Any]] = Field(..., description="MongoDB aggregation pipeline stages")


class InsertOneRequest(BaseActionRequest):
    document: Dict[str, Any] = Field(..., description="Document to insert")


class InsertManyRequest(BaseActionRequest):
    documents: List[Dict[str, Any]] = Field(..., description="Array of documents to insert")


class UpdateOneRequest(BaseActionRequest):
    filter: Dict[str, Any] = Field(..., description="Filter identifying document to update")
    update: Dict[str, Any] = Field(..., description="Update operations (e.g. {'$set': {...}})")
    upsert: bool = Field(False, description="Insert new document if no match found")


class UpdateManyRequest(BaseActionRequest):
    filter: Dict[str, Any] = Field(..., description="Filter identifying documents to update")
    update: Dict[str, Any] = Field(..., description="Update operations (e.g. {'$set': {...}})")
    upsert: bool = Field(False, description="Insert new document if no match found")


class DeleteOneRequest(BaseActionRequest):
    filter: Dict[str, Any] = Field(..., description="Filter identifying document to delete")


class DeleteManyRequest(BaseActionRequest):
    filter: Dict[str, Any] = Field(..., description="Filter identifying documents to delete")


# ==================== READ ENDPOINTS ====================


@router.post("/find")
async def find(
    req: FindRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Find documents matching query filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter) or {}
    projection = parse_ejson(req.projection)

    cursor = col.find(query_filter, projection=projection)
    if req.sort:
        cursor = cursor.sort(list(req.sort.items()))
    if req.skip:
        cursor = cursor.skip(req.skip)
    if req.limit:
        cursor = cursor.limit(req.limit)

    documents = await cursor.to_list(length=req.limit)
    return {"documents": serialize_bson(documents)}


@router.post("/findOne")
async def find_one(
    req: FindOneRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Find a single document matching query filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter) or {}
    projection = parse_ejson(req.projection)

    document = await col.find_one(query_filter, projection=projection)
    return {"document": serialize_bson(document)}


@router.post("/count")
async def count(
    req: CountRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Count documents matching filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter) or {}
    count_docs = await col.count_documents(query_filter)
    return {"count": count_docs}


@router.post("/aggregate")
async def aggregate(
    req: AggregateRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Execute aggregation pipeline."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    pipeline = parse_ejson(req.pipeline)
    cursor = col.aggregate(pipeline)
    documents = await cursor.to_list(length=1000)
    return {"documents": serialize_bson(documents)}


# ==================== MUTATION ENDPOINTS ====================


@router.post("/insertOne", status_code=status.HTTP_201_CREATED)
async def insert_one(
    req: InsertOneRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Insert a single document into collection."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    doc = parse_ejson(req.document)
    result = await col.insert_one(doc)
    return {"insertedId": str(result.inserted_id)}


@router.post("/insertMany", status_code=status.HTTP_201_CREATED)
async def insert_many(
    req: InsertManyRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Insert multiple documents into collection."""
    if not req.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="documents array cannot be empty",
        )

    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    docs = parse_ejson(req.documents)
    result = await col.insert_many(docs)
    return {"insertedIds": [str(x) for x in result.inserted_ids]}


@router.post("/updateOne")
async def update_one(
    req: UpdateOneRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Update a single document matching filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter)
    update_doc = parse_ejson(req.update)

    result = await col.update_one(query_filter, update_doc, upsert=req.upsert)
    response = {
        "matchedCount": result.matched_count,
        "modifiedCount": result.modified_count,
    }
    if result.upserted_id:
        response["upsertedId"] = str(result.upserted_id)
    return response


@router.post("/updateMany")
async def update_many(
    req: UpdateManyRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Update multiple documents matching filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter)
    update_doc = parse_ejson(req.update)

    result = await col.update_many(query_filter, update_doc, upsert=req.upsert)
    response = {
        "matchedCount": result.matched_count,
        "modifiedCount": result.modified_count,
    }
    if result.upserted_id:
        response["upsertedId"] = str(result.upserted_id)
    return response


@router.post("/deleteOne")
async def delete_one(
    req: DeleteOneRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Delete a single document matching filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter)
    result = await col.delete_one(query_filter)
    return {"deletedCount": result.deleted_count}


@router.post("/deleteMany")
async def delete_many(
    req: DeleteManyRequest,
    custom_uri: Optional[str] = Depends(get_custom_mongo_uri),
):
    """Delete multiple documents matching filter."""
    db = get_database(req.database, custom_uri)
    col = db[req.collection]

    query_filter = parse_ejson(req.filter)
    result = await col.delete_many(query_filter)
    return {"deletedCount": result.deleted_count}
