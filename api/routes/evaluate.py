"""
POST /evaluate endpoint

Triggers the asynchronous Celery task for the Equilibrium Engine.
"""

import logging
from fastapi import APIRouter, HTTPException

from ..schemas import EvaluationRequest, EvaluationResponse, TaskStatusResponse, ScoreOutput
from tasks.ml_worker import run_evaluation_task
from celery.result import AsyncResult

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("", response_model=EvaluationResponse)
async def evaluate_user(request: EvaluationRequest) -> EvaluationResponse:
    """
    Accepts a multimodal payload and triggers the async ML inference task.
    Returns a task_id immediately.
    """
    logger.info(f"Triggering evaluation task for user {request.user_id}")
    
    payload = {
        "upi_id": request.upi_id,
        "phone_number": request.phone_number,
        "file_metadata": request.file_metadata
    }
    
    # Trigger Celery Task
    task = run_evaluation_task.delay(request.user_id, payload)
    
    return EvaluationResponse(
        task_id=task.id,
        status="processing"
    )

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Polls Redis to check if the ML model has finished.
    """
    task_result = AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    
    if task_result.ready():
        if task_result.successful():
            response["result"] = task_result.result
        else:
            response["status"] = "FAILURE"
            response["error"] = str(task_result.result)
    else:
        # Include metadata/info if available (for progress tracking)
        if isinstance(task_result.info, dict):
            response["meta"] = task_result.info
            
    return TaskStatusResponse(**response)

@router.get("/results/{user_id}", response_model=ScoreOutput)
async def get_user_results(user_id: str) -> ScoreOutput:
    """
    Fetches the final score, SHAP explanations, and Neighborhood Graph JSON.
    In a real app, this would fetch the most recent completed task result from PostgreSQL.
    Here, we assume the frontend will use the data returned in /status directly,
    or we can provide a mock fetch if necessary.
    """
    raise HTTPException(status_code=501, detail="Fetch from DB not implemented. Use /status/{task_id} to get results.")
