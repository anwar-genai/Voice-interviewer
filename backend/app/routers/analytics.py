from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

router = APIRouter(prefix="/analytics", tags=["analytics"])


class InterviewSession(BaseModel):
    session_id: str
    job_title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    questions_asked: int = 0
    candidate_responses: int = 0
    overall_score: Optional[int] = None
    feedback: Optional[Dict[str, Any]] = None


class SessionAnalytics(BaseModel):
    total_sessions: int
    average_duration: float
    average_score: float
    most_common_roles: List[Dict[str, Any]]
    improvement_trends: List[Dict[str, Any]]


# In-memory storage (replace with database in production)
interview_sessions: Dict[str, InterviewSession] = {}


@router.post("/session/start")
async def start_session(session_data: Dict[str, Any]):
    """Start tracking an interview session."""
    session_id = session_data.get("session_id", f"session_{datetime.now().timestamp()}")
    
    session = InterviewSession(
        session_id=session_id,
        job_title=session_data.get("job_title", "Unknown"),
        start_time=datetime.now()
    )
    
    interview_sessions[session_id] = session
    return {"session_id": session_id, "status": "started"}


@router.post("/session/end")
async def end_session(session_data: Dict[str, Any]):
    """End tracking an interview session."""
    session_id = session_data.get("session_id")
    if not session_id or session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = interview_sessions[session_id]
    session.end_time = datetime.now()
    session.duration_minutes = int((session.end_time - session.start_time).total_seconds() / 60)
    session.questions_asked = session_data.get("questions_asked", 0)
    session.candidate_responses = session_data.get("candidate_responses", 0)
    session.overall_score = session_data.get("overall_score")
    session.feedback = session_data.get("feedback")
    
    return {"status": "completed", "duration_minutes": session.duration_minutes}


@router.get("/sessions", response_model=List[InterviewSession])
async def get_all_sessions():
    """Get all interview sessions."""
    return list(interview_sessions.values())


@router.get("/analytics", response_model=SessionAnalytics)
async def get_session_analytics():
    """Get analytics for all sessions."""
    sessions = list(interview_sessions.values())
    completed_sessions = [s for s in sessions if s.end_time is not None]
    
    if not completed_sessions:
        return SessionAnalytics(
            total_sessions=0,
            average_duration=0,
            average_score=0,
            most_common_roles=[],
            improvement_trends=[]
        )
    
    # Calculate averages
    avg_duration = sum(s.duration_minutes or 0 for s in completed_sessions) / len(completed_sessions)
    scored_sessions = [s for s in completed_sessions if s.overall_score is not None]
    avg_score = sum(s.overall_score for s in scored_sessions) / len(scored_sessions) if scored_sessions else 0
    
    # Most common roles
    role_counts = {}
    for session in completed_sessions:
        role = session.job_title
        role_counts[role] = role_counts.get(role, 0) + 1
    
    most_common_roles = [
        {"role": role, "count": count} 
        for role, count in sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    return SessionAnalytics(
        total_sessions=len(completed_sessions),
        average_duration=round(avg_duration, 2),
        average_score=round(avg_score, 2),
        most_common_roles=most_common_roles,
        improvement_trends=[]  # Could be enhanced with historical data
    )


@router.get("/session/{session_id}", response_model=InterviewSession)
async def get_session(session_id: str):
    """Get a specific session."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return interview_sessions[session_id]


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del interview_sessions[session_id]
    return {"status": "deleted"}
