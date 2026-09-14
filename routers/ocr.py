"""Receipt OCR via OCR.space (optional; only enabled when OCR_SPACE_API_KEY is set)."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

import config
from auth import require_auth
from money import parse_receipt_total

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/api/ocr")
async def ocr(image: UploadFile = File(...)):
    if not config.OCR_KEY:
        raise HTTPException(400, "OCR is not configured on the server")
    import httpx
    data = await image.read()
    files = {"file": (image.filename or "receipt.jpg", data, image.content_type or "image/jpeg")}
    form = {"apikey": config.OCR_KEY, "OCREngine": "2", "isTable": "true", "scale": "true"}
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post("https://api.ocr.space/parse/image", data=form, files=files)
        j = resp.json()
    except Exception:
        raise HTTPException(502, "Could not reach the OCR service")
    if j.get("IsErroredOnProcessing"):
        raise HTTPException(502, (j.get("ErrorMessage") or ["OCR failed"])[0])
    text = "\n".join(p.get("ParsedText", "") for p in (j.get("ParsedResults") or []))
    merchant = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return {"amount_paise": parse_receipt_total(text), "merchant": merchant[:40]}
