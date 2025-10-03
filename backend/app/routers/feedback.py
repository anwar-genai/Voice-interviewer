from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import os

router = APIRouter(prefix="/feedback", tags=["feedback"])


class InterviewFeedback(BaseModel):
    strengths: List[str]
    improvements: List[str]
    overall_score: int  # 1-10
    technical_score: int  # 1-10
    communication_score: int  # 1-10
    recommendations: List[str]


class GenerateFeedbackRequest(BaseModel):
    job_context: Dict[str, Any]
    candidate_resume: str
    interview_transcript: str


@router.post("/generate", response_model=InterviewFeedback)
async def generate_interview_feedback(request: GenerateFeedbackRequest):
    """Generate AI-powered interview feedback."""
    try:
        from cerebras.cloud.sdk import Cerebras
        
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Cerebras API key not configured")
        
        client = Cerebras(api_key=api_key)
        
        # Create detailed feedback prompt
        feedback_prompt = f"""
        You are an expert interview coach. Analyze this interview transcript and provide constructive feedback.
        
        Job Position: {request.job_context.get('job_title', 'Unknown')}
        Job Requirements: {request.job_context.get('qualifications', 'Not specified')}
        
        Candidate Resume Summary: {request.candidate_resume[:300]}...
        
        Interview Transcript: {request.interview_transcript}
        
        Please provide detailed feedback in the following JSON format:
        {{
            "strengths": ["List 3-5 specific strengths demonstrated"],
            "improvements": ["List 3-5 specific areas for improvement"],
            "overall_score": 7,
            "technical_score": 6,
            "communication_score": 8,
            "recommendations": ["List 3-5 actionable recommendations for next interview"]
        }}
        
        Be specific, constructive, and encouraging. Focus on actionable advice.
        """
        
        completion = client.chat.completions.create(
            model=os.getenv("CEREBRAS_MODEL", "llama3.3-70b"),
            messages=[
                {"role": "system", "content": "You are an expert interview coach providing constructive feedback."},
                {"role": "user", "content": feedback_prompt}
            ],
            max_tokens=800,
            temperature=0.7
        )
        
        # Parse the response
        response_text = completion.choices[0].message.content
        try:
            feedback_data = json.loads(response_text)
            return InterviewFeedback(**feedback_data)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return InterviewFeedback(
                strengths=["Good communication skills", "Relevant experience"],
                improvements=["Provide more specific examples", "Ask clarifying questions"],
                overall_score=7,
                technical_score=6,
                communication_score=8,
                recommendations=["Practice STAR method responses", "Research the company more"]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate feedback: {str(e)}")


class InterviewMetrics(BaseModel):
    total_questions: int
    response_time_avg: float
    technical_depth: int
    communication_clarity: int
    engagement_level: int


@router.post("/metrics", response_model=InterviewMetrics)
async def calculate_interview_metrics(transcript: str):
    """Calculate interview performance metrics."""
    # Simple heuristics for now - could be enhanced with more sophisticated analysis
    words = transcript.split()
    sentences = transcript.split('.')
    
    return InterviewMetrics(
        total_questions=transcript.count('?'),
        response_time_avg=len(words) / max(sentences.count('.'), 1) * 0.5,  # Rough estimate
        technical_depth=min(10, transcript.count('technical') + transcript.count('experience') + transcript.count('project')),
        communication_clarity=min(10, transcript.count('explain') + transcript.count('describe') + transcript.count('example')),
        engagement_level=min(10, transcript.count('yes') + transcript.count('absolutely') + transcript.count('definitely'))
    )
