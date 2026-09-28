from pydantic import BaseModel
from typing import Optional


class InsightQuestion(BaseModel):
    question: str


class InsightAnswerOut(BaseModel):
    question: str
    answer: str
    category: str
    source: str
    provider: str
    supporting_data: Optional[dict] = None
    records: list[dict] = []
