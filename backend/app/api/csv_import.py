from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.csv_import import import_properties_csv
from app.schemas.csv_import import ImportResult

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB — generous for a CSV, small enough to reject accidental huge uploads


def _status_and_message(result: dict) -> tuple[str, str]:
    total = result["total_rows"]
    valid = result["valid_rows"]
    rejected = result["rejected_rows"]

    if result.get("import_error"):
        return "error", f"Import failed and was rolled back — no changes were made. ({result['import_error']})"
    if total == 0:
        return "empty", "The CSV had a valid header but no data rows to import."
    if valid == 0:
        return "rejected", f"All {total} row(s) failed validation and were not imported."
    if rejected == 0:
        return "success", f"All {total} row(s) imported successfully."
    return "partial", f"{valid} of {total} row(s) imported; {rejected} row(s) were rejected."


@router.post("/csv", response_model=ImportResult)
async def upload_csv(db: Session = Depends(get_db), file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit.")

    result = import_properties_csv(db, contents, file.filename)

    if result.get("structural_error"):
        raise HTTPException(status_code=400, detail=result["structural_error"])

    status, message = _status_and_message(result)

    return ImportResult(
        filename=result["filename"],
        status=status,
        total_rows=result["total_rows"],
        valid_rows=result["valid_rows"],
        rejected_rows=result["rejected_rows"],
        imported_property_ids=result["imported_property_ids"],
        issue_counts=result["issue_counts"],
        row_issues=result["row_issues"],
        message=message,
    )
