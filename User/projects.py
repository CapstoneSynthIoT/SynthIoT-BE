from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import uuid as uuid_module
from datetime import datetime

from Database_files.database import get_db
from Database_files.models import Project, User
from Database_files.cloudstorage import replace_in_bucket

router = APIRouter(prefix="/projects", tags=["Projects"])


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    user_id: UUID
    title: str
    icon: Optional[str] = None
    prompt: Optional[str] = None
    tags: Optional[list[str]] = None
    datapoints_count: Optional[int] = 0
    csv_link: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Schema for updating a project. csv_link is intentionally excluded."""
    title: Optional[str] = None
    icon: Optional[str] = None
    prompt: Optional[str] = None
    tags: Optional[list[str]] = None
    datapoints_count: Optional[int] = None


class ProjectResponse(BaseModel):
    uuid: UUID
    user_id: UUID
    title: str
    icon: Optional[str]
    prompt: Optional[str]
    created_on: Optional[datetime]
    last_active: Optional[datetime]
    tags: Optional[list[str]]
    datapoints_count: Optional[int]
    csv_link: Optional[str]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# CRUD Endpoints
# ─────────────────────────────────────────────

@router.post("/", response_model=ProjectResponse, status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project. user_id must reference an existing user."""
    # Validate that the user exists
    user = db.query(User).filter(User.uuid == project.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {project.user_id} not found.")

    new_project = Project(
        uuid=uuid_module.uuid4(),
        user_id=project.user_id,
        title=project.title,
        icon=project.icon,
        prompt=project.prompt,
        tags=project.tags,
        datapoints_count=project.datapoints_count,
        csv_link=project.csv_link,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


@router.get("/", response_model=list[ProjectResponse])
def get_all_projects(db: Session = Depends(get_db)):
    """Return all projects."""
    return db.query(Project).all()


@router.get("/user/{user_id}", response_model=list[ProjectResponse])
def get_projects_by_user(user_id: UUID, db: Session = Depends(get_db)):
    """Return all projects belonging to a specific user."""
    user = db.query(User).filter(User.uuid == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return db.query(Project).filter(Project.user_id == user_id).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    """Return a single project by its UUID."""
    project = db.query(Project).filter(Project.uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: UUID, updates: ProjectUpdate, db: Session = Depends(get_db)):
    """
    Update editable project fields.
    csv_link is NOT included here — it is set automatically by the /generate endpoint.
    """
    project = db.query(Project).filter(Project.uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    """Delete a project by its UUID."""
    project = db.query(Project).filter(Project.uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")

    db.delete(project)
    db.commit()


@router.patch("/{project_id}/csv", response_model=ProjectResponse)
async def update_project_csv(project_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Replace the CSV stored in GCS for a project.
    Uploads the new file in-place using the blob name extracted from the project's
    existing csv_link — the URL stays the same after the overwrite.
    """
    project = db.query(Project).filter(Project.uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")

    if not project.csv_link:
        raise HTTPException(
            status_code=400,
            detail="This project has no csv_link set yet. Use POST /projects/ or PATCH /projects/{id} to set one first."
        )

    # Extract blob name from the GCS URL
    # URL format: https://storage.googleapis.com/{bucket}/{blob_name}
    try:
        blob_name = project.csv_link.split("/", maxsplit=4)[-1]
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse blob name from the project's csv_link.")

    file_bytes = await file.read()
    new_url = await run_in_threadpool(replace_in_bucket, file_bytes, blob_name)

    # csv_link stays the same (same blob), but refresh last_active via a touch
    project.csv_link = new_url
    db.commit()
    db.refresh(project)
    return project
