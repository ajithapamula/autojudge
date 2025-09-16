import os, httpx
FIGMA_TOKEN = os.getenv("FIGMA_TOKEN")

async def get_file(file_key: str | None):
    if not file_key: return None
    headers = {"X-Figma-Token": FIGMA_TOKEN} if FIGMA_TOKEN else {}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"https://api.figma.com/v1/files/{file_key}", headers=headers)
        r.raise_for_status()
        return r.json()
