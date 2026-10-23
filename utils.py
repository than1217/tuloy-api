from fastapi import Request, Response
from typing import Optional
import hashlib
import re

def cache_key_builder(
    func,
    namespace: str = "",
    *,
    request: Optional[Request] = None,
    response: Optional[Response] = None,
    args: tuple = (),
    kwargs: Optional[dict] = None,
) -> str:
    """Build deterministic cache keys excluding per-request DB/auth dependency objects."""
    filtered_kwargs = {
        k: v
        for k, v in (kwargs or {}).items()
        if k not in ("db", "current_user")
    }
    raw_key = f"{func.__module__}:{func.__name__}:{args}:{sorted(filtered_kwargs.items())}"
    key_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
    return f"{namespace}:{key_hash}"

def generate_md5_hash(first_name: str, last_name: str, dob: str) -> str:
    """Generate MD5 hash from the inputs to match the database match_keys format."""
    first_clean = re.sub(r'\\s+', ' ', first_name).strip().upper()
    last_clean = re.sub(r'\\s+', ' ', last_name).strip().upper()
    raw_string = f"{first_clean}/{last_clean}/{dob}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()
