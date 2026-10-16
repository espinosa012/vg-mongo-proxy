from __future__ import annotations

import base64
import datetime
from typing import Any, Dict, List, Union

from bson import ObjectId, json_util


def parse_ejson(data: Any) -> Any:
    """Recursively parse JSON payload into BSON-compatible types.

    Converts:
    - {"$oid": "..."} -> ObjectId
    - {"$date": "..."} -> datetime
    - "_id": "24hexcharacters" -> ObjectId (for developer convenience)
    - Nested dictionaries and lists
    """
    if data is None:
        return None

    if isinstance(data, dict):
        # Handle Extended JSON $oid
        if len(data) == 1 and "$oid" in data and isinstance(data["$oid"], str):
            try:
                return ObjectId(data["$oid"])
            except Exception:
                return data

        # Handle Extended JSON $date
        if len(data) == 1 and "$date" in data:
            try:
                val = data["$date"]
                if isinstance(val, (int, float)):
                    return datetime.datetime.fromtimestamp(val / 1000.0, tz=datetime.timezone.utc)
                if isinstance(val, str):
                    # Remove trailing Z for fromisoformat if needed
                    iso_str = val.replace("Z", "+00:00")
                    return datetime.datetime.fromisoformat(iso_str)
            except Exception:
                return data

        parsed: Dict[str, Any] = {}
        for k, v in data.items():
            # Auto-convert _id string to ObjectId if 24 hex characters
            if k == "_id" and isinstance(v, str) and len(v) == 24:
                try:
                    parsed[k] = ObjectId(v)
                    continue
                except Exception:
                    pass

            # Auto-convert arrays of IDs in $in / $nin under _id
            if k in ("$in", "$nin") and isinstance(v, list):
                parsed[k] = [
                    ObjectId(x) if (isinstance(x, str) and len(x) == 24 and ObjectId.is_valid(x)) else parse_ejson(x)
                    for x in v
                ]
                continue

            parsed[k] = parse_ejson(v)
        return parsed

    if isinstance(data, list):
        return [parse_ejson(item) for item in data]

    return data


def serialize_bson(obj: Any) -> Any:
    """Recursively serialize BSON objects to JSON-friendly native Python types.

    Converts:
    - ObjectId -> str (24-hex string)
    - datetime / date -> ISO 8601 string
    - bytes / Binary -> base64 string
    """
    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, (datetime.datetime, datetime.date)):
        if isinstance(obj, datetime.datetime) and obj.tzinfo is None:
            obj = obj.replace(tzinfo=datetime.timezone.utc)
        return obj.isoformat()

    if isinstance(obj, (bytes, bytearray)):
        return base64.b64encode(obj).decode("ascii")

    if isinstance(obj, dict):
        return {k: serialize_bson(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [serialize_bson(item) for item in obj]

    return obj
