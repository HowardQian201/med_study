"""
Pydantic models for FastAPI endpoints
"""
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# Auth models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    success: bool

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str # Add name field

class AuthCheckResponse(BaseModel):
    authenticated: bool
    user: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None

# PDF and content models
class GenerateSummaryRequest(BaseModel):
    userText: Optional[str] = ""
    selectedPdfHashes: List[str] = []
    isQuizMode: Optional[str] = "false"

class RegenerateSummaryRequest(BaseModel):
    userText: Optional[str] = ""
    selectedPdfHashes: List[str] = []

class SaveSummaryRequest(BaseModel):
    summary: str

# Quiz models
class GenerateQuizRequest(BaseModel):
    type: str = "initial"  # 'initial', 'focused', or 'additional'
    incorrectQuestionIds: Optional[List[str]] = None
    previousQuestions: Optional[List[Dict[str, Any]]] = None
    isPreviewing: Optional[bool] = None
    numQuestions: int = 5
    isQuizMode: Optional[str] = "false"
    diff_mode: Optional[bool] = False

class SaveQuizAnswersRequest(BaseModel):
    userAnswers: Dict[str, int]
    submittedAnswers: Dict[str, bool]

class ToggleStarQuestionRequest(BaseModel):
    questionId: str

class StarAllQuestionsRequest(BaseModel):
    action: str  # 'star' or 'unstar'

# Study set models
class LoadStudySetRequest(BaseModel):
    content_hash: str

class UpdateSetTitleRequest(BaseModel):
    content_hash: str
    new_title: str

class DeleteQuestionSetRequest(BaseModel):
    content_hash: str

class DeleteQuestionsRequest(BaseModel):
    content_hash: str
    question_hashes: List[str]

class LoadStudySetResponse(BaseModel):
    success: bool
    summary: str
    content_hash: str
    other_content_hash: str

# PDF management models
class RemoveUserPdfsRequest(BaseModel):
    pdf_hashes: List[str]

# Feedback model
class SubmitFeedbackRequest(BaseModel):
    feedback: str

# Response models
class SuccessResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str

class UserPdfsResponse(BaseModel):
    success: bool
    pdfs: List[Dict[str, Any]]

class QuestionSetsResponse(BaseModel):
    success: bool
    sets: List[Dict[str, Any]]

class QuizResponse(BaseModel):
    success: bool
    questions: List[Dict[str, Any]]
    short_summary: Optional[str] = None
    content_hash: Optional[str] = None
    other_content_hash: Optional[str] = None

class CurrentSessionSourcesResponse(BaseModel):
    success: bool
    content_names: List[str]
    short_summary: str

class UserTasksResponse(BaseModel):
    success: bool
    tasks: List[Dict[str, Any]]

class UploadResponse(BaseModel):
    success: bool
    message: str
    uploaded_files: List[Dict[str, Any]]
    failed_files: List[Dict[str, Any]]
    task_details: List[Dict[str, Any]]

class TaskStatusResponse(BaseModel):
    success: bool
    task_id: str
    status: str
    result: Optional[Any] = None
    message: str

# Additional response models for remaining endpoints
class UpdateSetTitleResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class QuestionResponse(BaseModel):
    success: bool
    question: Dict[str, Any]

class ShuffleQuizResponse(BaseModel):
    success: bool
    questions: List[Dict[str, Any]]

class StarredQuizResponse(BaseModel):
    success: bool
    questions: List[Dict[str, Any]]
    error: Optional[str] = None

class StarAllQuestionsResponse(BaseModel):
    success: bool
    questions: List[Dict[str, Any]]
