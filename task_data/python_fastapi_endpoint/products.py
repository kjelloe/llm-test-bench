from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()


class ProductIn(BaseModel):
    name: str
    price: float
    # BUG: no Field(gt=0) constraint on price — accepts zero and negative values


class Product(BaseModel):
    id: int
    name: str
    price: float


_db: dict[int, Product] = {}
_next_id = 1


@app.post("/products")  # BUG: missing status_code=201
def create_product(body: ProductIn) -> Product:
    global _next_id
    # BUG: no validation that name is not empty/whitespace
    product = Product(id=_next_id, name=body.name.strip(), price=body.price)
    _db[_next_id] = product
    _next_id += 1
    return product


@app.get("/products/{product_id}")
def get_product(product_id: int) -> Product:
    # BUG: returns None when not found, causing a 500 instead of 404
    return _db.get(product_id)  # type: ignore[return-value]
