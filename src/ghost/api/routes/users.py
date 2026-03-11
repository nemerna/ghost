"""User management API endpoints."""

import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr

from ghost.api.deps import CurrentUser, require_admin, require_manager_or_admin
from ghost.db import User, UserRole, get_db

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class UserResponse(BaseModel):
    """User response model."""
    
    id: int
    email: str
    display_name: str | None
    role: str
    preferences: dict
    first_seen: str | None
    last_seen: str | None
    
    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """Request model for updating a user."""
    
    display_name: str | None = None
    role: str | None = None  # Only admins can change roles


class PreferencesUpdateRequest(BaseModel):
    """Request model for updating user preferences."""
    
    preferences: dict


class VisibilitySettings(BaseModel):
    """Visibility settings for manager access."""
    
    activity_logs: str = "shared"  # "shared" or "private"
    management_reports: str = "private"


class VisibilitySettingsResponse(BaseModel):
    """Response model for visibility settings."""
    
    visibility_defaults: VisibilitySettings


class UserListResponse(BaseModel):
    """Response model for user list."""
    
    users: list[UserResponse]
    total: int


# =============================================================================
# Email Distribution Template Models
# =============================================================================


class EmailDistributionTemplate(BaseModel):
    """Email distribution template for sending reports via Gmail."""
    
    id: str  # Unique template ID (UUID)
    name: str  # Template name (e.g., "Platform Team Weekly")
    recipients: list[str]  # Array of email addresses
    subject_template: str  # Subject line with placeholders (e.g., "{{team_name}} - {{period}}")
    included_field_ids: list[int] = []  # Field IDs to include (empty = all)
    included_project_ids: list[int] = []  # Project IDs to include (empty = all in selected fields)
    created_at: str | None = None
    updated_at: str | None = None


class EmailTemplateCreateRequest(BaseModel):
    """Request model for creating an email template."""
    
    name: str
    recipients: list[str]
    subject_template: str
    included_field_ids: list[int] = []
    included_project_ids: list[int] = []


class EmailTemplateUpdateRequest(BaseModel):
    """Request model for updating an email template."""
    
    name: str | None = None
    recipients: list[str] | None = None
    subject_template: str | None = None
    included_field_ids: list[int] | None = None
    included_project_ids: list[int] | None = None


class EmailTemplateListResponse(BaseModel):
    """Response model for email template list."""
    
    templates: list[EmailDistributionTemplate]
    total: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: CurrentUser):
    """Get the current authenticated user's information."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value if user.role else "user",
        preferences=json.loads(user.preferences) if user.preferences else {},
        first_seen=user.first_seen.isoformat() if user.first_seen else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
    )


@router.put("/me/preferences", response_model=UserResponse)
async def update_my_preferences(
    user: CurrentUser,
    request: PreferencesUpdateRequest,
):
    """Update the current user's preferences."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        db_user.preferences = json.dumps(request.preferences)
        session.flush()
        
        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            display_name=db_user.display_name,
            role=db_user.role.value if db_user.role else "user",
            preferences=request.preferences,
            first_seen=db_user.first_seen.isoformat() if db_user.first_seen else None,
            last_seen=db_user.last_seen.isoformat() if db_user.last_seen else None,
        )


@router.get("/me/visibility", response_model=VisibilitySettingsResponse)
async def get_my_visibility_settings(user: CurrentUser):
    """Get the current user's visibility settings for manager access."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        visibility_defaults = preferences.get("visibility_defaults", {})
        
        return VisibilitySettingsResponse(
            visibility_defaults=VisibilitySettings(
                activity_logs=visibility_defaults.get("activity_logs", "shared"),
                management_reports=visibility_defaults.get("management_reports", "private"),
            )
        )


@router.put("/me/visibility", response_model=VisibilitySettingsResponse)
async def update_my_visibility_settings(
    user: CurrentUser,
    settings: VisibilitySettings,
):
    """Update the current user's visibility settings for manager access."""
    db = get_db()
    
    # Validate values
    valid_values = {"shared", "private"}
    if settings.activity_logs not in valid_values:
        raise HTTPException(status_code=400, detail="activity_logs must be 'shared' or 'private'")
    if settings.management_reports not in valid_values:
        raise HTTPException(status_code=400, detail="management_reports must be 'shared' or 'private'")
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get existing preferences and update visibility_defaults
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        preferences["visibility_defaults"] = {
            "activity_logs": settings.activity_logs,
            "management_reports": settings.management_reports,
        }
        db_user.preferences = json.dumps(preferences)
        session.flush()
        
        return VisibilitySettingsResponse(
            visibility_defaults=settings
        )


@router.get("", response_model=UserListResponse)
async def list_users(
    user: Annotated[User, Depends(require_manager_or_admin)],
    search: str | None = Query(None, description="Search by email or display name"),
    role: str | None = Query(None, description="Filter by role"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all users (managers and admins only)."""
    db = get_db()
    
    with db.session() as session:
        query = session.query(User)
        
        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (User.email.ilike(search_pattern)) | 
                (User.display_name.ilike(search_pattern))
            )
        
        # Apply role filter
        if role:
            try:
                role_enum = UserRole(role)
                query = query.filter(User.role == role_enum)
            except ValueError:
                pass  # Invalid role, ignore filter
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        users = query.order_by(User.email).offset(offset).limit(limit).all()
        
        return UserListResponse(
            users=[
                UserResponse(
                    id=u.id,
                    email=u.email,
                    display_name=u.display_name,
                    role=u.role.value if u.role else "user",
                    preferences=json.loads(u.preferences) if u.preferences else {},
                    first_seen=u.first_seen.isoformat() if u.first_seen else None,
                    last_seen=u.last_seen.isoformat() if u.last_seen else None,
                )
                for u in users
            ],
            total=total,
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Get a specific user by ID (managers and admins only)."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            display_name=db_user.display_name,
            role=db_user.role.value if db_user.role else "user",
            preferences=json.loads(db_user.preferences) if db_user.preferences else {},
            first_seen=db_user.first_seen.isoformat() if db_user.first_seen else None,
            last_seen=db_user.last_seen.isoformat() if db_user.last_seen else None,
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Update a user (admin only)."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update display name if provided
        if request.display_name is not None:
            db_user.display_name = request.display_name
        
        # Update role if provided (admin only)
        if request.role is not None:
            try:
                db_user.role = UserRole(request.role)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}",
                )
        
        session.flush()
        
        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            display_name=db_user.display_name,
            role=db_user.role.value if db_user.role else "user",
            preferences=json.loads(db_user.preferences) if db_user.preferences else {},
            first_seen=db_user.first_seen.isoformat() if db_user.first_seen else None,
            last_seen=db_user.last_seen.isoformat() if db_user.last_seen else None,
        )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    user: Annotated[User, Depends(require_admin)],
):
    """Delete a user (admin only)."""
    db = get_db()
    
    # Prevent self-deletion
    if user_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account",
        )
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        session.delete(db_user)
    
    return {"message": f"User {user_id} deleted successfully"}


# =============================================================================
# Email Distribution Template Endpoints
# =============================================================================


def _get_email_templates(preferences: dict) -> list[dict]:
    """Extract email templates from user preferences."""
    return preferences.get("email_templates", [])


def _set_email_templates(preferences: dict, templates: list[dict]) -> dict:
    """Update email templates in user preferences."""
    preferences["email_templates"] = templates
    return preferences


@router.get("/me/email-templates", response_model=EmailTemplateListResponse)
async def list_email_templates(user: CurrentUser):
    """List the current user's email distribution templates."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        templates = _get_email_templates(preferences)
        
        return EmailTemplateListResponse(
            templates=[EmailDistributionTemplate(**t) for t in templates],
            total=len(templates),
        )


@router.post("/me/email-templates", response_model=EmailDistributionTemplate, status_code=status.HTTP_201_CREATED)
async def create_email_template(
    request: EmailTemplateCreateRequest,
    user: CurrentUser,
):
    """Create a new email distribution template."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        templates = _get_email_templates(preferences)
        
        # Check for duplicate name
        if any(t["name"] == request.name for t in templates):
            raise HTTPException(
                status_code=400,
                detail=f"Template with name '{request.name}' already exists",
            )
        
        # Create new template
        now = datetime.utcnow().isoformat()
        new_template = {
            "id": str(uuid.uuid4()),
            "name": request.name,
            "recipients": request.recipients,
            "subject_template": request.subject_template,
            "included_field_ids": request.included_field_ids,
            "included_project_ids": request.included_project_ids,
            "created_at": now,
            "updated_at": now,
        }
        
        templates.append(new_template)
        db_user.preferences = json.dumps(_set_email_templates(preferences, templates))
        session.flush()
        
        return EmailDistributionTemplate(**new_template)


@router.get("/me/email-templates/{template_id}", response_model=EmailDistributionTemplate)
async def get_email_template(
    template_id: str,
    user: CurrentUser,
):
    """Get a specific email distribution template."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        templates = _get_email_templates(preferences)
        
        template = next((t for t in templates if t["id"] == template_id), None)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return EmailDistributionTemplate(**template)


@router.put("/me/email-templates/{template_id}", response_model=EmailDistributionTemplate)
async def update_email_template(
    template_id: str,
    request: EmailTemplateUpdateRequest,
    user: CurrentUser,
):
    """Update an existing email distribution template."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        templates = _get_email_templates(preferences)
        
        # Find template
        template_idx = next((i for i, t in enumerate(templates) if t["id"] == template_id), None)
        if template_idx is None:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template = templates[template_idx]
        
        # Check for duplicate name (if name is being changed)
        if request.name is not None and request.name != template["name"]:
            if any(t["name"] == request.name for t in templates):
                raise HTTPException(
                    status_code=400,
                    detail=f"Template with name '{request.name}' already exists",
                )
        
        # Update fields
        if request.name is not None:
            template["name"] = request.name
        if request.recipients is not None:
            template["recipients"] = request.recipients
        if request.subject_template is not None:
            template["subject_template"] = request.subject_template
        if request.included_field_ids is not None:
            template["included_field_ids"] = request.included_field_ids
        if request.included_project_ids is not None:
            template["included_project_ids"] = request.included_project_ids
        
        template["updated_at"] = datetime.utcnow().isoformat()
        
        templates[template_idx] = template
        db_user.preferences = json.dumps(_set_email_templates(preferences, templates))
        session.flush()
        
        return EmailDistributionTemplate(**template)


@router.delete("/me/email-templates/{template_id}")
async def delete_email_template(
    template_id: str,
    user: CurrentUser,
):
    """Delete an email distribution template."""
    db = get_db()
    
    with db.session() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(db_user.preferences) if db_user.preferences else {}
        templates = _get_email_templates(preferences)
        
        # Find and remove template
        template_idx = next((i for i, t in enumerate(templates) if t["id"] == template_id), None)
        if template_idx is None:
            raise HTTPException(status_code=404, detail="Template not found")
        
        templates.pop(template_idx)
        db_user.preferences = json.dumps(_set_email_templates(preferences, templates))
        session.flush()
    
    return {"message": "Template deleted successfully"}
