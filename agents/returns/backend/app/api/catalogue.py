"""Product catalogue API.

Admins manage catalogue entries (product metadata, default expected components,
identifying features). Authenticated users may read the catalogue (needed by
inspection interfaces to show expected products).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.returns.backend.app.auth.deps import client_ip, get_current_user, require_admin
from agents.returns.backend.app.core.errors import ConflictError, NotFoundError
from agents.returns.backend.app.db.session import get_db
from agents.returns.backend.app.models import AuditAction, CatalogueProduct, User
from agents.returns.backend.app.schemas import CatalogueProductIn, CatalogueProductOut
from agents.returns.backend.app.services.audit_service import record_event

router = APIRouter(prefix="/api/catalogue", tags=["catalogue"])


@router.get("", response_model=list[CatalogueProductOut])
def list_catalogue(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(CatalogueProduct).order_by(CatalogueProduct.created_at.desc())))


@router.post("", response_model=CatalogueProductOut, status_code=201)
def create_product(
    payload: CatalogueProductIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sku = payload.sku.strip().upper()
    if db.scalar(select(CatalogueProduct).where(CatalogueProduct.sku == sku)) is not None:
        raise ConflictError("A catalogue product with this SKU already exists.", code="sku_taken")
    product = CatalogueProduct(
        sku=sku,
        name=payload.name.strip(),
        description=payload.description.strip(),
        default_components=[
            {
                "name": c.name.strip(),
                "yolo_class_hints": c.yolo_class_hints,
                "ocr_text_hint": c.ocr_text_hint,
            }
            for c in payload.default_components
        ],
        identifying_features=[f.strip() for f in payload.identifying_features if f.strip()],
        created_by_id=admin.id,
    )
    db.add(product)
    db.flush()
    record_event(
        db, action=AuditAction.CATALOGUE_CREATED, entity_type="catalogue_product", entity_id=product.id,
        actor_id=admin.id, actor_role=admin.role, details={"sku": sku}, ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=CatalogueProductOut)
def update_product(
    product_id: str,
    payload: CatalogueProductIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.get(CatalogueProduct, product_id)
    if product is None:
        raise NotFoundError("Catalogue product not found.", code="not_found")
    sku = payload.sku.strip().upper()
    if sku != product.sku and db.scalar(select(CatalogueProduct).where(CatalogueProduct.sku == sku)) is not None:
        raise ConflictError("A catalogue product with this SKU already exists.", code="sku_taken")
    product.sku = sku
    product.name = payload.name.strip()
    product.description = payload.description.strip()
    product.default_components = [
        {"name": c.name.strip(), "yolo_class_hints": c.yolo_class_hints, "ocr_text_hint": c.ocr_text_hint}
        for c in payload.default_components
    ]
    product.identifying_features = [f.strip() for f in payload.identifying_features if f.strip()]
    record_event(
        db, action=AuditAction.CATALOGUE_UPDATED, entity_type="catalogue_product", entity_id=product.id,
        actor_id=admin.id, actor_role=admin.role, details={"sku": sku}, ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(product)
    return product
