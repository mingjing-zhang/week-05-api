from typing import Optional

import anthropic
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base, Book
from schemas import BookCreate, BookUpdate, BookResponse

# Create the books table on startup if it doesn't already exist.
Base.metadata.create_all(bind=engine)

# AI client — reads ANTHROPIC_API_KEY from environment (loaded by load_dotenv in database.py).
# Using Haiku 4.5 for cost: ~$1/M input + $5/M output, ~3x cheaper than Sonnet for this lab's volume.
ai_client = anthropic.Anthropic()
AI_MODEL = "claude-haiku-4-5"

app = FastAPI(title="Book Tracker API", version="2.0.0")

# Allow the Next.js dev server (localhost:3000) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to Book Tracker API"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/books", response_model=list[BookResponse])
def get_books(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Book)
    if status:
        query = query.filter(Book.status == status)
    return query.all()


@app.get("/books/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Book.id)).scalar()

    rows = db.query(Book.status, func.count(Book.id)).group_by(Book.status).all()
    count_by_status = {status: count for status, count in rows}

    avg = db.query(func.avg(Book.rating)).filter(Book.rating.isnot(None)).scalar()
    average_rating = float(avg) if avg is not None else 0

    return {
        "total": total,
        "count_by_status": count_by_status,
        "average_rating": average_rating,
    }


@app.get("/books/{book_id}", response_model=BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", response_model=BookResponse, status_code=201)
def create_book(data: BookCreate, db: Session = Depends(get_db)):
    book = Book(**data.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@app.put("/books/{book_id}", response_model=BookResponse)
def update_book(book_id: int, updates: BookUpdate, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    for field, value in updates.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


@app.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(book)
    db.commit()
    return {"message": "Book deleted", "id": book_id}


# ----------------------------------------------------------------------
# AI endpoints (Week 5 lab additions)
# ----------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Inbound chat request. conversation_history is a list of
    {"role": "user"|"assistant", "content": str} dicts kept on the client."""
    message: str
    conversation_history: list[dict] = []


@app.post("/ai/chat")
def chat_with_assistant(request: ChatRequest):
    """General-purpose book-aware chat. Does NOT know the user's library —
    use /ai/recommend for personalized recommendations."""
    messages = request.conversation_history + [
        {"role": "user", "content": request.message}
    ]

    response = ai_client.messages.create(
        model=AI_MODEL,
        max_tokens=1024,
        system=(
            "You are a helpful book assistant for a personal book tracking app. "
            "Help users discover books, discuss what they've read, and get "
            "personalized recommendations. Be conversational, enthusiastic about "
            "books, and concise in your responses."
        ),
        messages=messages,
    )

    reply = response.content[0].text

    return {
        "reply": reply,
        "updated_history": messages + [{"role": "assistant", "content": reply}],
    }


@app.post("/ai/recommend")
def get_recommendations(request: ChatRequest, db: Session = Depends(get_db)):
    """Personalized book recommendations grounded in the user's actual library
    fetched from Postgres on each call (so recommendations stay fresh as the
    user adds/finishes books)."""
    # Fetch all books from the database
    books = db.query(Book).all()

    # Build a summary of the user's library
    read_books = [b for b in books if b.status == "read"]
    reading_books = [b for b in books if b.status == "reading"]

    book_context = "Here is the user's book library:\n"

    if read_books:
        book_context += "\nBooks they've read:\n"
        for b in read_books:
            rating_str = f" (rated {b.rating}/5)" if b.rating else ""
            book_context += f"- {b.title} by {b.author}{rating_str}\n"

    if reading_books:
        book_context += "\nCurrently reading:\n"
        for b in reading_books:
            book_context += f"- {b.title} by {b.author}\n"

    if not read_books and not reading_books:
        book_context += "No books tracked yet.\n"

    system_prompt = (
        "You are a personalized book recommendation assistant.\n\n"
        f"{book_context}\n"
        "Based on this reading history, provide thoughtful, personalized "
        "recommendations. Be specific about why each recommendation matches "
        "their taste. Keep responses concise — 2-3 recommendations at most "
        "unless asked for more."
    )

    messages = request.conversation_history + [
        {"role": "user", "content": request.message}
    ]

    response = ai_client.messages.create(
        model=AI_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )

    reply = response.content[0].text
    return {
        "reply": reply,
        "updated_history": messages + [{"role": "assistant", "content": reply}],
    }
