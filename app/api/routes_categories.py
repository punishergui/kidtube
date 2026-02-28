from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models import Category
from app.db.session import get_session

router = APIRouter()


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    enabled: bool = True
    daily_limit_minutes: int | None = Field(default=None, ge=0)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None
    daily_limit_minutes: int | None = Field(default=None, ge=0)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool
    daily_limit_minutes: int | None
    created_at: datetime


@router.get("", response_model=list[CategoryRead])
def list_categories(
    session: Session = Depends(get_session),
    include_disabled: bool = Query(default=False),
) -> list[Category]:
    query = select(Category)
    if not include_disabled:
        query = query.where(Category.enabled.is_(True))
    return session.exec(query.order_by(Category.id)).all()


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, session: Session = Depends(get_session)) -> Category:
    category_name = payload.name.strip()
    if not category_name:
        raise HTTPException(status_code=400, detail="Category name cannot be blank")

    existing_category = session.exec(select(Category).where(Category.name == category_name)).first()
    if existing_category:
        raise HTTPException(status_code=409, detail="Category name must be unique")

    category = Category.model_validate(payload.model_copy(update={"name": category_name}))
    session.add(category)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category name must be unique") from None
    session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
def patch_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
) -> Category:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    updates = payload.model_dump(exclude_unset=True)
    new_name = updates.get("name")
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Category name cannot be blank")
        updates["name"] = new_name

    if new_name and new_name != category.name:
        existing_category = session.exec(select(Category).where(Category.name == new_name)).first()
        if existing_category:
            raise HTTPException(status_code=409, detail="Category name must be unique")

    for field, value in updates.items():
        setattr(category, field, value)

    session.add(category)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category name must be unique") from None
    session.refresh(category)
    return category


@router.delete("/{category_id}", response_model=CategoryRead)
def disable_category(
    category_id: int,
    archive: bool = Query(default=False),
    hard_delete: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> Category:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    in_use = bool(
        session.execute(
            text("SELECT 1 FROM channels WHERE category_id = :category_id LIMIT 1"),
            {"category_id": category_id},
        ).first()
        or session.execute(
            text("SELECT 1 FROM watch_log WHERE category_id = :category_id LIMIT 1"),
            {"category_id": category_id},
        ).first()
    )

    if in_use and not archive:
        raise HTTPException(status_code=409, detail="Category is in use; archive instead")

    if hard_delete and not in_use:
        session.delete(category)
        session.commit()
        return CategoryRead.model_validate(
            {
                "id": category_id,
                "name": category.name,
                "enabled": False,
                "daily_limit_minutes": category.daily_limit_minutes,
                "created_at": category.created_at,
            }
        )

    category.enabled = False
    session.add(category)
    session.commit()
    session.refresh(category)
    return category
