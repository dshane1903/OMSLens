from typing import Any

import httpx


async def post_json(url: str, payload: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
