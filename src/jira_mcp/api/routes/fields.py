"""Report field and project configuration API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from jira_mcp.api.deps import CurrentUser, require_admin
from jira_mcp.db import (
    ProjectGitRepo,
    ProjectJiraComponent,
    ReportField,
    ReportProject,
    User,
    get_db,
)
from jira_mcp.tools.reports import redetect_project_assignments

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class JiraComponentConfig(BaseModel):
    """Jira component configuration for a project."""

    jira_project_key: str
    component_name: str


class ProjectResponse(BaseModel):
    """Project response model."""

    id: int
    field_id: int
    name: str
    description: str | None
    display_order: int
    git_repos: list[str]
    jira_components: list[JiraComponentConfig]
    created_at: str | None
    updated_at: str | None


class FieldResponse(BaseModel):
    """Field response model."""

    id: int
    name: str
    description: str | None
    display_order: int
    projects: list[ProjectResponse]
    created_at: str | None
    updated_at: str | None


class FieldListResponse(BaseModel):
    """Response model for field list."""

    fields: list[FieldResponse]
    total: int


class FieldCreateRequest(BaseModel):
    """Request model for creating a field."""

    name: str
    description: str | None = None


class FieldUpdateRequest(BaseModel):
    """Request model for updating a field."""

    name: str | None = None
    description: str | None = None


class FieldReorderRequest(BaseModel):
    """Request model for reordering fields."""

    field_ids: list[int]  # List of field IDs in desired order


class ProjectCreateRequest(BaseModel):
    """Request model for creating a project."""

    name: str
    description: str | None = None
    git_repos: list[str] | None = None
    jira_components: list[JiraComponentConfig] | None = None


class ProjectUpdateRequest(BaseModel):
    """Request model for updating a project."""

    name: str | None = None
    description: str | None = None
    git_repos: list[str] | None = None
    jira_components: list[JiraComponentConfig] | None = None


class ProjectReorderRequest(BaseModel):
    """Request model for reordering projects within a field."""

    project_ids: list[int]  # List of project IDs in desired order


class RedetectResponse(BaseModel):
    """Response model for redetection operation."""

    success: bool
    processed_count: int
    updated_count: int
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def field_to_response(field: ReportField) -> FieldResponse:
    """Convert ReportField model to response."""
    return FieldResponse(
        id=field.id,
        name=field.name,
        description=field.description,
        display_order=field.display_order,
        projects=[project_to_response(p) for p in sorted(field.projects, key=lambda x: x.display_order)],
        created_at=field.created_at.isoformat() if field.created_at else None,
        updated_at=field.updated_at.isoformat() if field.updated_at else None,
    )


def project_to_response(project: ReportProject) -> ProjectResponse:
    """Convert ReportProject model to response."""
    return ProjectResponse(
        id=project.id,
        field_id=project.field_id,
        name=project.name,
        description=project.description,
        display_order=project.display_order,
        git_repos=[r.repo_pattern for r in project.git_repos],
        jira_components=[
            JiraComponentConfig(
                jira_project_key=c.jira_project_key,
                component_name=c.component_name,
            )
            for c in project.jira_components
        ],
        created_at=project.created_at.isoformat() if project.created_at else None,
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
    )


# =============================================================================
# Field Endpoints
# =============================================================================


@router.get("", response_model=FieldListResponse)
async def list_fields(user: CurrentUser):
    """List all report fields with their projects."""
    db = get_db()

    with db.session() as session:
        fields = (
            session.query(ReportField)
            .order_by(ReportField.display_order)
            .all()
        )

        return FieldListResponse(
            fields=[field_to_response(f) for f in fields],
            total=len(fields),
        )


@router.post("", response_model=FieldResponse, status_code=status.HTTP_201_CREATED)
async def create_field(
    request: FieldCreateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Create a new report field (admin only)."""
    db = get_db()

    with db.session() as session:
        # Check for duplicate name
        existing = session.query(ReportField).filter(ReportField.name == request.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field with name '{request.name}' already exists",
            )

        # Get max display_order
        max_order = session.query(ReportField.display_order).order_by(
            ReportField.display_order.desc()
        ).first()
        new_order = (max_order[0] + 1) if max_order else 0

        field = ReportField(
            name=request.name,
            description=request.description,
            display_order=new_order,
            created_at=datetime.utcnow(),
        )
        session.add(field)
        session.flush()

        return field_to_response(field)


@router.get("/{field_id}", response_model=FieldResponse)
async def get_field(field_id: int, user: CurrentUser):
    """Get a specific report field."""
    db = get_db()

    with db.session() as session:
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        return field_to_response(field)


@router.put("/{field_id}", response_model=FieldResponse)
async def update_field(
    field_id: int,
    request: FieldUpdateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Update a report field (admin only)."""
    db = get_db()

    with db.session() as session:
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        if request.name is not None:
            # Check for duplicate name
            existing = (
                session.query(ReportField)
                .filter(ReportField.name == request.name, ReportField.id != field_id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field with name '{request.name}' already exists",
                )
            field.name = request.name

        if request.description is not None:
            field.description = request.description

        field.updated_at = datetime.utcnow()
        session.flush()

        return field_to_response(field)


@router.delete("/{field_id}")
async def delete_field(
    field_id: int,
    user: Annotated[User, Depends(require_admin)],
):
    """Delete a report field and all its projects (admin only)."""
    db = get_db()

    with db.session() as session:
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        session.delete(field)

    return {"message": f"Field '{field.name}' deleted successfully"}


@router.put("/reorder", response_model=FieldListResponse)
async def reorder_fields(
    request: FieldReorderRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Reorder report fields (admin only)."""
    db = get_db()

    with db.session() as session:
        # Verify all field IDs exist
        fields = session.query(ReportField).filter(ReportField.id.in_(request.field_ids)).all()
        if len(fields) != len(request.field_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more field IDs not found",
            )

        # Update display_order based on position in list
        field_map = {f.id: f for f in fields}
        for order, field_id in enumerate(request.field_ids):
            field_map[field_id].display_order = order
            field_map[field_id].updated_at = datetime.utcnow()

        session.flush()

        # Return updated list
        all_fields = session.query(ReportField).order_by(ReportField.display_order).all()
        return FieldListResponse(
            fields=[field_to_response(f) for f in all_fields],
            total=len(all_fields),
        )


# =============================================================================
# Project Endpoints
# =============================================================================


@router.post("/{field_id}/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    field_id: int,
    request: ProjectCreateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Create a new project within a field (admin only)."""
    db = get_db()

    with db.session() as session:
        # Verify field exists
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        # Check for duplicate name within field
        existing = (
            session.query(ReportProject)
            .filter(ReportProject.field_id == field_id, ReportProject.name == request.name)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with name '{request.name}' already exists in this field",
            )

        # Get max display_order within field
        max_order = (
            session.query(ReportProject.display_order)
            .filter(ReportProject.field_id == field_id)
            .order_by(ReportProject.display_order.desc())
            .first()
        )
        new_order = (max_order[0] + 1) if max_order else 0

        project = ReportProject(
            field_id=field_id,
            name=request.name,
            description=request.description,
            display_order=new_order,
            created_at=datetime.utcnow(),
        )
        session.add(project)
        session.flush()

        # Add git repos
        if request.git_repos:
            for repo_pattern in request.git_repos:
                git_repo = ProjectGitRepo(
                    project_id=project.id,
                    repo_pattern=repo_pattern,
                )
                session.add(git_repo)

        # Add Jira components
        if request.jira_components:
            for comp in request.jira_components:
                jira_comp = ProjectJiraComponent(
                    project_id=project.id,
                    jira_project_key=comp.jira_project_key,
                    component_name=comp.component_name,
                )
                session.add(jira_comp)

        session.flush()
        session.refresh(project)

        return project_to_response(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, user: CurrentUser):
    """Get a specific project."""
    db = get_db()

    with db.session() as session:
        project = session.query(ReportProject).filter(ReportProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return project_to_response(project)


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Update a project including its git repos and Jira components (admin only)."""
    db = get_db()

    with db.session() as session:
        project = session.query(ReportProject).filter(ReportProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if request.name is not None:
            # Check for duplicate name within field
            existing = (
                session.query(ReportProject)
                .filter(
                    ReportProject.field_id == project.field_id,
                    ReportProject.name == request.name,
                    ReportProject.id != project_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Project with name '{request.name}' already exists in this field",
                )
            project.name = request.name

        if request.description is not None:
            project.description = request.description

        # Update git repos (replace all)
        if request.git_repos is not None:
            # Delete existing
            session.query(ProjectGitRepo).filter(ProjectGitRepo.project_id == project_id).delete()
            # Add new
            for repo_pattern in request.git_repos:
                git_repo = ProjectGitRepo(
                    project_id=project_id,
                    repo_pattern=repo_pattern,
                )
                session.add(git_repo)

        # Update Jira components (replace all)
        if request.jira_components is not None:
            # Delete existing
            session.query(ProjectJiraComponent).filter(
                ProjectJiraComponent.project_id == project_id
            ).delete()
            # Add new
            for comp in request.jira_components:
                jira_comp = ProjectJiraComponent(
                    project_id=project_id,
                    jira_project_key=comp.jira_project_key,
                    component_name=comp.component_name,
                )
                session.add(jira_comp)

        project.updated_at = datetime.utcnow()
        session.flush()
        session.refresh(project)

        return project_to_response(project)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    user: Annotated[User, Depends(require_admin)],
):
    """Delete a project (admin only)."""
    db = get_db()

    with db.session() as session:
        project = session.query(ReportProject).filter(ReportProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_name = project.name
        session.delete(project)

    return {"message": f"Project '{project_name}' deleted successfully"}


@router.put("/{field_id}/projects/reorder", response_model=FieldResponse)
async def reorder_projects(
    field_id: int,
    request: ProjectReorderRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Reorder projects within a field (admin only)."""
    db = get_db()

    with db.session() as session:
        # Verify field exists
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        # Verify all project IDs exist and belong to this field
        projects = (
            session.query(ReportProject)
            .filter(
                ReportProject.id.in_(request.project_ids),
                ReportProject.field_id == field_id,
            )
            .all()
        )
        if len(projects) != len(request.project_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more project IDs not found or don't belong to this field",
            )

        # Update display_order based on position in list
        project_map = {p.id: p for p in projects}
        for order, project_id in enumerate(request.project_ids):
            project_map[project_id].display_order = order
            project_map[project_id].updated_at = datetime.utcnow()

        session.flush()
        session.refresh(field)

        return field_to_response(field)


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.post("/redetect", response_model=RedetectResponse)
async def redetect_activities(
    user: Annotated[User, Depends(require_admin)],
    username: str | None = None,
    limit: int = 1000,
):
    """Re-run project detection on existing activities (admin only).
    
    Useful after changing field/project configuration.
    """
    result = redetect_project_assignments(username=username, limit=limit)
    return RedetectResponse(**result)
