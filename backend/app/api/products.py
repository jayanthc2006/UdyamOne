"""Catalogue product API routes."""

from fastapi import APIRouter, HTTPException, status

from app.models.product import Product
from app.schemas.catalogue import ProductListResponse
from app.services.catalogue_loader import load_catalogue

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def list_products() -> ProductListResponse:
    """Return every product in the current catalogue."""
    return ProductListResponse(products=load_catalogue())


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: str) -> Product:
    """Return one product or a not-found response."""
    for product in load_catalogue():
        if product.product_id == product_id:
            return product
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Product '{product_id}' was not found.",
    )
