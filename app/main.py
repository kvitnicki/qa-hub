from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="QA Portfolio API",
    description="Simple API for QA/CI-CD portfolio project",
    version="0.1.0",
)


class Item(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: float
    in_stock: bool = True


# In-memory storage (для учебного проекта)
items_db: dict[int, Item] = {}


@app.get("/")
def root():
    return {"message": "QA Portfolio API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/items", response_model=list[Item])
def get_items():
    return list(items_db.values())


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]


@app.post("/items", response_model=Item, status_code=201)
def create_item(item: Item):
    if item.id in items_db:
        raise HTTPException(status_code=400, detail="Item already exists")
    items_db[item.id] = item
    return item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    del items_db[item_id]
    return None
