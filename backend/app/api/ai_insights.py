from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ai_insights import answer_question, get_provider_name, EXAMPLE_QUESTIONS
from app.schemas.ai_insights import InsightQuestion, InsightAnswerOut

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/ask", response_model=InsightAnswerOut)
def ask_question(payload: InsightQuestion, db: Session = Depends(get_db)):
    result = answer_question(db, payload.question)
    return InsightAnswerOut(
        question=result.question,
        answer=result.answer,
        category=result.category,
        source=result.source,
        provider=get_provider_name(),
        supporting_data=result.supporting_data,
        records=result.records,
    )


@router.get("/examples")
def get_examples():
    return {"examples": EXAMPLE_QUESTIONS, "provider": get_provider_name()}
