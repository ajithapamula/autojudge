import re, httpx, textstat

async def fetch_text(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(url)
            if r.status_code != 200: return None
            html = r.text
            text = re.sub(r"<[^>]+>", " ", html)
            return re.sub(r"\s+", " ", text)[:6000]
    except: return None

def readability_points(text: str) -> int:
    try:
        fk = textstat.flesch_kincaid_grade(text)
        return 25 if fk<=8 else 18 if fk<=12 else 12
    except: return 15

def count_keywords(text: str, kws: list[str]) -> int:
    t = text.lower()
    return sum(k in t for k in kws)
