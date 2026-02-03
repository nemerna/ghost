"""Report field and project configuration API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ghost.api.deps import CurrentUser, require_admin
from ghost.db import (
    ProjectGitRepo,
    ProjectJiraComponent,
    ReportField,
    ReportProject,
    User,
    get_db,
)
from ghost.tools.reports import redetect_project_assignments

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class JiraComponentConfig(BaseModel):
    """Jira component configuration for a project."""

    jira_project_key: str
    component_name: str


class ProjectResponse(BaseModel):
    """Project response model with hierarchical support."""

    id: int
    field_id: int
    parent_id: int | None
    name: str
    description: str | None
    display_order: int
    is_leaf: bool
    git_repos: list[str]
    jira_components: list[JiraComponentConfig]
    children: list["ProjectResponse"]
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
    """Request model for creating a project.
    
    If parent_id is provided, creates a subproject under that parent.
    Git repos and Jira components should only be set on leaf projects.
    """

    name: str
    description: str | None = None
    parent_id: int | None = None
    git_repos: list[str] | None = None
    jira_components: list[JiraComponentConfig] | None = None


class ProjectUpdateRequest(BaseModel):
    """Request model for updating a project.
    
    parent_id can be changed to move a project in the hierarchy.
    Git repos and Jira components should only be set on leaf projects.
    """

    name: str | None = None
    description: str | None = None
    parent_id: int | None = None
    git_repos: list[str] | None = None
    jira_components: list[JiraComponentConfig] | None = None


class ProjectReorderRequest(BaseModel):
    """Request model for reordering projects within a parent (or field if top-level)."""

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
    """Convert ReportField model to response with hierarchical projects."""
    # Only include top-level projects (parent_id is None)
    # Children are nested within each project
    top_level_projects = [p for p in field.projects if p.parent_id is None]
    return FieldResponse(
        id=field.id,
        name=field.name,
        description=field.description,
        display_order=field.display_order,
        projects=[
            project_to_response(p) 
            for p in sorted(top_level_projects, key=lambda x: x.display_order)
        ],
        created_at=field.created_at.isoformat() if field.created_at else None,
        updated_at=field.updated_at.isoformat() if field.updated_at else None,
    )


def project_to_response(project: ReportProject) -> ProjectResponse:
    """Convert ReportProject model to response with nested children."""
    return ProjectResponse(
        id=project.id,
        field_id=project.field_id,
        parent_id=project.parent_id,
        name=project.name,
        description=project.description,
        display_order=project.display_order,
        is_leaf=project.is_leaf,
        git_repos=[r.repo_pattern for r in project.git_repos],
        jira_components=[
            JiraComponentConfig(
                jira_project_key=c.jira_project_key,
                component_name=c.component_name,
            )
            for c in project.jira_components
        ],
        children=[
            project_to_response(c) 
            for c in sorted(project.children, key=lambda x: x.display_order)
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
    """Create a new project within a field (admin only).
    
    If parent_id is provided, creates a subproject under that parent.
    Git repos and Jira components should only be configured on leaf projects.
    """
    db = get_db()

    with db.session() as session:
        # Verify field exists
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        parent_project = None
        if request.parent_id is not None:
            # Verify parent project exists and belongs to the same field
            parent_project = session.query(ReportProject).filter(
                ReportProject.id == request.parent_id
            ).first()
            if not parent_project:
                raise HTTPException(status_code=404, detail="Parent project not found")
            if parent_project.field_id != field_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent project must belong to the same field",
                )
            
            # If parent has detection mappings, warn that they won't be used
            # (detection only happens on leaf nodes)
            if parent_project.git_repos or parent_project.jira_components:
                # Clear parent's detection mappings since it's no longer a leaf
                session.query(ProjectGitRepo).filter(
                    ProjectGitRepo.project_id == parent_project.id
                ).delete()
                session.query(ProjectJiraComponent).filter(
                    ProjectJiraComponent.project_id == parent_project.id
                ).delete()

        # Check for duplicate name within same parent (or field if top-level)
        existing = (
            session.query(ReportProject)
            .filter(
                ReportProject.field_id == field_id, 
                ReportProject.parent_id == request.parent_id,
                ReportProject.name == request.name
            )
            .first()
        )
        if existing:
            parent_info = f" under '{parent_project.name}'" if parent_project else ""
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with name '{request.name}' already exists{parent_info} in this field",
            )

        # Get max display_order within same parent (or field if top-level)
        max_order_query = session.query(ReportProject.display_order).filter(
            ReportProject.field_id == field_id,
            ReportProject.parent_id == request.parent_id,
        )
        max_order = max_order_query.order_by(ReportProject.display_order.desc()).first()
        new_order = (max_order[0] + 1) if max_order else 0

        project = ReportProject(
            field_id=field_id,
            parent_id=request.parent_id,
            name=request.name,
            description=request.description,
            display_order=new_order,
            created_at=datetime.utcnow(),
        )
        session.add(project)
        session.flush()

        # Add git repos (only for leaf projects - this new project is a leaf)
        if request.git_repos:
            for repo_pattern in request.git_repos:
                git_repo = ProjectGitRepo(
                    project_id=project.id,
                    repo_pattern=repo_pattern,
                )
                session.add(git_repo)

        # Add Jira components (only for leaf projects - this new project is a leaf)
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
        
        # Refresh parent if we modified it
        if parent_project:
            session.refresh(parent_project)

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


def _check_circular_reference(project_id: int, new_parent_id: int, session) -> bool:
    """Check if setting new_parent_id would create a circular reference."""
    if new_parent_id is None:
        return False
    
    # Walk up the parent chain from new_parent_id
    current_id = new_parent_id
    visited = set()
    while current_id is not None:
        if current_id == project_id:
            return True  # Circular reference detected
        if current_id in visited:
            break  # Already checked this (shouldn't happen but safety check)
        visited.add(current_id)
        parent = session.query(ReportProject.parent_id).filter(
            ReportProject.id == current_id
        ).first()
        current_id = parent[0] if parent else None
    return False


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Update a project including its git repos and Jira components (admin only).
    
    Can also change parent_id to move the project in the hierarchy.
    Git repos and Jira components can only be set on leaf projects (no children).
    """
    db = get_db()

    with db.session() as session:
        project = session.query(ReportProject).filter(ReportProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Handle parent_id change (moving project in hierarchy)
        if request.parent_id is not None and request.parent_id != project.parent_id:
            # Can't set parent_id to self
            if request.parent_id == project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A project cannot be its own parent",
                )
            
            # Verify new parent exists and belongs to same field
            new_parent = session.query(ReportProject).filter(
                ReportProject.id == request.parent_id
            ).first()
            if not new_parent:
                raise HTTPException(status_code=404, detail="New parent project not found")
            if new_parent.field_id != project.field_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent project must belong to the same field",
                )
            
            # Check for circular reference
            if _check_circular_reference(project_id, request.parent_id, session):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set parent: would create a circular reference",
                )
            
            # If new parent has detection mappings, clear them (no longer a leaf)
            if new_parent.git_repos or new_parent.jira_components:
                session.query(ProjectGitRepo).filter(
                    ProjectGitRepo.project_id == new_parent.id
                ).delete()
                session.query(ProjectJiraComponent).filter(
                    ProjectJiraComponent.project_id == new_parent.id
                ).delete()
            
            project.parent_id = request.parent_id
        elif hasattr(request, 'parent_id') and request.parent_id is None and project.parent_id is not None:
            # Explicitly setting parent_id to None (making it top-level)
            project.parent_id = None

        if request.name is not None:
            # Check for duplicate name within same parent
            existing = (
                session.query(ReportProject)
                .filter(
                    ReportProject.field_id == project.field_id,
                    ReportProject.parent_id == project.parent_id,
                    ReportProject.name == request.name,
                    ReportProject.id != project_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Project with name '{request.name}' already exists at this level",
                )
            project.name = request.name

        if request.description is not None:
            project.description = request.description

        # Check if project is a leaf before allowing detection mappings
        # Need to refresh to get current children count
        session.flush()
        session.refresh(project)
        
        has_children = len(project.children) > 0

        # Update git repos (replace all) - only allowed on leaf projects
        if request.git_repos is not None:
            if has_children and len(request.git_repos) > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Git repos can only be configured on leaf projects (projects without children)",
                )
            # Delete existing
            session.query(ProjectGitRepo).filter(ProjectGitRepo.project_id == project_id).delete()
            # Add new
            for repo_pattern in request.git_repos:
                git_repo = ProjectGitRepo(
                    project_id=project_id,
                    repo_pattern=repo_pattern,
                )
                session.add(git_repo)

        # Update Jira components (replace all) - only allowed on leaf projects
        if request.jira_components is not None:
            if has_children and len(request.jira_components) > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Jira components can only be configured on leaf projects (projects without children)",
                )
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
    """Delete a project and all its children recursively (admin only).
    
    This will cascade delete all subprojects, their detection mappings,
    and clear detected_project_id references in activity logs.
    """
    db = get_db()

    with db.session() as session:
        project = session.query(ReportProject).filter(ReportProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_name = project.name
        children_count = len(project.children)
        
        # Clear detected_project_id for activities pointing to this project or its children
        # This is handled by ON DELETE SET NULL in the FK, but we do it explicitly for clarity
        from ghost.db import ActivityLog
        
        def get_all_descendant_ids(proj) -> list[int]:
            """Recursively get all descendant project IDs."""
            ids = [proj.id]
            for child in proj.children:
                ids.extend(get_all_descendant_ids(child))
            return ids
        
        all_ids = get_all_descendant_ids(project)
        session.query(ActivityLog).filter(
            ActivityLog.detected_project_id.in_(all_ids)
        ).update({ActivityLog.detected_project_id: None}, synchronize_session=False)
        
        session.delete(project)

    message = f"Project '{project_name}' deleted successfully"
    if children_count > 0:
        message += f" (including {children_count} child project(s))"
    return {"message": message}


@router.put("/{field_id}/projects/reorder", response_model=FieldResponse)
async def reorder_projects(
    field_id: int,
    request: ProjectReorderRequest,
    user: Annotated[User, Depends(require_admin)],
    parent_id: int | None = None,
):
    """Reorder projects within a field at a specific parent level (admin only).
    
    If parent_id is provided, reorders children of that parent.
    If parent_id is None, reorders top-level projects in the field.
    """
    db = get_db()

    with db.session() as session:
        # Verify field exists
        field = session.query(ReportField).filter(ReportField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")

        # If parent_id provided, verify it exists and belongs to this field
        if parent_id is not None:
            parent = session.query(ReportProject).filter(
                ReportProject.id == parent_id,
                ReportProject.field_id == field_id,
            ).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent project not found in this field")

        # Verify all project IDs exist, belong to this field, and share the same parent
        projects = (
            session.query(ReportProject)
            .filter(
                ReportProject.id.in_(request.project_ids),
                ReportProject.field_id == field_id,
                ReportProject.parent_id == parent_id,
            )
            .all()
        )
        if len(projects) != len(request.project_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more project IDs not found, don't belong to this field, or don't share the same parent",
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
