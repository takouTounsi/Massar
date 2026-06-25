from fastapi import HTTPException, Request


async def enforce_payload_size(request: Request, max_bytes: int = 200_000) -> None:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
