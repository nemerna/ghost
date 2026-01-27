"""User management API endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr

from jira_mcp.api.deps import CurrentUser, require_admin, require_manager_or_admin
from jira_mcp.db import User, UserRole, get_db

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
    weekly_reports: str = "shared"
    management_reports: str = "private"


class VisibilitySettingsResponse(BaseModel):
    """Response model for visibility settings."""
    
    visibility_defaults: VisibilitySettings


class UserListResponse(BaseModel):
    """Response model for user list."""
    
    users: list[UserResponse]
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
                weekly_reports=visibility_defaults.get("weekly_reports", "shared"),
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
    if settings.weekly_reports not in valid_values:
        raise HTTPException(status_code=400, detail="weekly_reports must be 'shared' or 'private'")
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
            "weekly_reports": settings.weekly_reports,
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
