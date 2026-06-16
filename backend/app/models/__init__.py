from app.models.department import Department
from app.models.cdl import CorsoDiLaurea
from app.models.syllabus import Syllabus
from app.models.evaluation import EvaluationResult
from app.models.local_document import LocalDocument
from app.models.evaluation_external_document import EvaluationExternalDocument
from app.models.user import AuthSession, User

__all__ = [
    "Department",
    "CorsoDiLaurea",
    "Syllabus",
    "EvaluationResult",
    "LocalDocument",
    "EvaluationExternalDocument",
    "User",
    "AuthSession",
]
