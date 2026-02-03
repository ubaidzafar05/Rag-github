from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from db_models import RepoIngestion, IngestJob
from schemas import IngestRequest, IngestStatus
from dependencies import get_optional_user_dep
from services.ingestion import clone_repo, run_repomix, crawl_docs, build_repo_index
import uuid

router = APIRouter(prefix="/ingest", tags=["ingestion"])

def get_repo_ingestion(db: Session, repo_url: str) -> RepoIngestion | None:
    return db.query(RepoIngestion).filter(RepoIngestion.repo_url == repo_url).first()

def process_ingestion(
    request: IngestRequest,
    db: Session | None,
    current_user: dict | None,
    job_id: str | None = None,
) -> dict:
    db_session = db or SessionLocal()
    try:
        repo_path = clone_repo(request.repo_url)
        packed_content = run_repomix(repo_path)

        if not packed_content:
            raise HTTPException(status_code=500, detail="Repomix failed to generate output.")

        docs_content = ""
        if request.docs_url:
            docs_content = crawl_docs(request.docs_url)
            packed_content += f"\n\n--- DOCUMENTATION ({request.docs_url}) ---\n{docs_content}"

        repo_index = build_repo_index(repo_path)

        ingestion = db_session.query(RepoIngestion).filter(RepoIngestion.repo_url == request.repo_url).first()
        if not ingestion:
            ingestion = RepoIngestion(
                repo_url=request.repo_url,
                user_id=current_user["id"] if current_user else None,
                repo_index=repo_index,
                content=packed_content,
                local_path=repo_path 
            )
            db_session.add(ingestion)
        else:
            ingestion.repo_index = repo_index
            ingestion.content = packed_content
            ingestion.user_id = ingestion.user_id or (current_user["id"] if current_user else None)
            ingestion.local_path = repo_path
        db_session.commit()
        
        if job_id:
            job = db_session.query(IngestJob).filter(IngestJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.current_step = "Completed"
                job.error_message = None
                db_session.commit()
                
        return {"status": "success", "message": "Repository ingested successfully", "size": len(packed_content)}
    except Exception as e:
        if job_id:
            job = db_session.query(IngestJob).filter(IngestJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.current_step = "Failed"
                db_session.commit()
        raise
    finally:
        if db is None:
            db_session.close()

@router.post("")
def ingest_endpoint(
    request: IngestRequest,
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user_dep),
):
    try:
        return process_ingestion(request, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/async", response_model=IngestStatus)
def ingest_async_endpoint(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user_dep),
):
    job_id = uuid.uuid4().hex
    
    job = IngestJob(
        id=job_id,
        repo_url=request.repo_url,
        status="running",
        current_step="Starting...",
        created_at=None # auto
    )
    db.add(job)
    db.commit()
    
    background_tasks.add_task(process_ingestion, request, None, current_user, job_id)
    return IngestStatus(job_id=job_id, status="running", repo_url=request.repo_url)

@router.get("/status/{job_id}", response_model=IngestStatus)
def ingest_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IngestStatus(
        job_id=job.id,
        status=job.status,
        message=job.current_step if job.status != "failed" else job.error_message,
        repo_url=job.repo_url,
    )
