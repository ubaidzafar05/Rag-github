from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from db_models import RepoIngestion
from schemas import ApplyRequest, ApplyPreviewRequest, ApplyValidateRequest, ApplyReviewRequest
from services.editor import apply_code_patch, generate_diff, run_validation

router = APIRouter(prefix="/apply", tags=["editor"])

def get_repo_ingestion(db: Session, repo_url: str) -> RepoIngestion | None:
    return db.query(RepoIngestion).filter(RepoIngestion.repo_url == repo_url).first()

@router.post("")
def apply_fix(request: ApplyRequest, db: Session = Depends(get_db)):
    ingestion = get_repo_ingestion(db, request.repo_url)
    if not ingestion or not ingestion.local_path:
        raise HTTPException(status_code=400, detail="Repository not ingested or path lost.")
    
    repo_path = ingestion.local_path
    
    try:
        if not request.approved:
            raise HTTPException(status_code=400, detail="Apply requires approved=true after review.")
        if request.validation_commands:
            results = run_validation(repo_path, request.validation_commands)
            failures = [result for result in results if result["returncode"] != 0]
            if failures:
                raise HTTPException(status_code=400, detail={"message": "Validation failed.", "results": results})
        apply_code_patch(repo_path, request.file_path, request.content)
        return {"status": "success", "message": f"Applied fix to {request.file_path}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preview")
def preview_fix(request: ApplyPreviewRequest, db: Session = Depends(get_db)):
    ingestion = get_repo_ingestion(db, request.repo_url)
    if not ingestion or not ingestion.local_path:
        raise HTTPException(status_code=400, detail="Repository not ingested.")
    repo_path = ingestion.local_path
    diff = generate_diff(repo_path, request.file_path, request.content)
    return {"status": "success", "diff": diff}

@router.post("/validate")
def validate_fix(request: ApplyValidateRequest, db: Session = Depends(get_db)):
    ingestion = get_repo_ingestion(db, request.repo_url)
    if not ingestion or not ingestion.local_path:
        raise HTTPException(status_code=400, detail="Repository not ingested.")
    repo_path = ingestion.local_path
    results = run_validation(repo_path, request.commands)
    return {"status": "success", "results": results}

@router.post("/review")
def review_fix(request: ApplyReviewRequest, db: Session = Depends(get_db)):
    ingestion = get_repo_ingestion(db, request.repo_url)
    if not ingestion or not ingestion.local_path:
        raise HTTPException(status_code=400, detail="Repository not ingested.")
    repo_path = ingestion.local_path
    diff = generate_diff(repo_path, request.file_path, request.content)
    results = []
    if request.validation_commands:
        results = run_validation(repo_path, request.validation_commands)
    return {"status": "success", "diff": diff, "results": results}
