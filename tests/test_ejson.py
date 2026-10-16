import datetime
from bson import ObjectId

from vg_mongo_proxy.utils.ejson import parse_ejson, serialize_bson


def test_parse_ejson_oid():
    raw = {"$oid": "60d5ec49f1b2c8b1f8e4e1a1"}
    parsed = parse_ejson(raw)
    assert isinstance(parsed, ObjectId)
    assert str(parsed) == "60d5ec49f1b2c8b1f8e4e1a1"


def test_parse_ejson_id_string():
    raw = {"_id": "60d5ec49f1b2c8b1f8e4e1a1", "title": "Buy milk"}
    parsed = parse_ejson(raw)
    assert isinstance(parsed["_id"], ObjectId)
    assert parsed["title"] == "Buy milk"


def test_parse_ejson_date():
    raw = {"$date": "2026-05-01T12:00:00Z"}
    parsed = parse_ejson(raw)
    assert isinstance(parsed, datetime.datetime)
    assert parsed.year == 2026


def test_serialize_bson():
    oid = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    now = datetime.datetime(2026, 10, 16, 21, 30, 0, tzinfo=datetime.timezone.utc)
    doc = {
        "_id": oid,
        "created_at": now,
        "items": [{"id": oid}],
        "binary": b"hello",
    }
    serialized = serialize_bson(doc)
    assert serialized["_id"] == "60d5ec49f1b2c8b1f8e4e1a1"
    assert serialized["created_at"] == "2026-10-16T21:30:00+00:00"
    assert serialized["items"][0]["id"] == "60d5ec49f1b2c8b1f8e4e1a1"
    assert serialized["binary"] == "aGVsbG8="
