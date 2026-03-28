# app/services/quiz_generator_service.py
import json
import secrets
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from fastapi import HTTPException, status
from app.database.database import settings
from app.services.embedding_service import retrieve_context


def generate_question_id() -> str:
    """Generate a unique question ID in format QUZ-XXXXXXXX."""
    random_hex = secrets.token_hex(4).upper()
    return f"QUZ-{random_hex}"


async def generate_quiz_questions(
    course_data: dict,
    knowledge_bases: Optional[List[str]] = None,
    user_instration: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate 10 quiz questions based on course lecture data using OpenAI.
    
    Args:
        course_data: The course lecture document from Course_lecture_generator
        
    Returns:
        List of 10 quiz question dictionaries
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured in .env",
        )

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


    course_name = course_data.get("generated_course_name", "")
    modules = course_data.get("modules", [])
    
    # Build comprehensive content summary
    content_summary = f"Course: {course_name}\n\n"
    for module in modules:
        module_title = module.get("title", "")
        content_summary += f"Module {module.get('module_number', '')}: {module_title}\n"
        content_summary += f"Introduction: {module.get('introduction', '')}\n\n"
        
        study_topics = module.get("study_topics", [])
        for topic in study_topics:
            topic_name = topic.get("topic_name", "")
            topic_data = topic.get("topic_wise_study_data", {})
            content_summary += f"  Topic: {topic_name}\n"
            content_summary += f"  Summary: {topic_data.get('summary', '')}\n"
            content_summary += f"  Details: {topic_data.get('detailed_explanation', '')}\n\n"

    instruction_block = f"\nUser Instruction:\n{user_instration}\n" if user_instration else ""
    rag_query = f"Quiz questions for {course_name} covering key concepts"
    rag_context = await retrieve_context(
        query=rag_query,
        knowledge_bases=knowledge_bases,
        top_k=6,
        max_chars=3500,
    )
    context_block = f"\nReference Context (from PDFs):\n{rag_context}\n" if rag_context else ""

    prompt = f"""You are an expert quiz creator for educational courses.

Based on the following course content, create 10 multiple-choice quiz questions that test understanding of the key concepts.

{content_summary}{instruction_block}{context_block}

Generate EXACTLY 10 quiz questions in the following JSON format:

{{
  "questions": [
    {{
      "question_number": 1,
      "question_text": "<clear, specific question>",
      "options": [
        {{"option_letter": "A", "option_text": "<option A text>"}},
        {{"option_letter": "B", "option_text": "<option B text>"}},
        {{"option_letter": "C", "option_text": "<option C text>"}},
        {{"option_letter": "D", "option_text": "<option D text>"}}
      ],
      "correct_answer": "<A, B, C, or D>"
    }}
  ]
}}

REQUIREMENTS:
- Create EXACTLY 10 questions (numbered 1-10)
- Each question must have EXACTLY 4 options (A, B, C, D)
- Questions should test understanding, not just memorization
- Cover content from different modules and topics
- Ensure only ONE correct answer per question
- Make incorrect options plausible but clearly wrong
- Questions should be clear and unambiguous
- Return ONLY valid JSON, no additional text or markdown"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert educational quiz creator. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000,
        )

        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        quiz_data = json.loads(content)
        questions = quiz_data.get("questions", [])

        if len(questions) != 10:
            raise ValueError(f"Expected 10 questions, got {len(questions)}")

        # Add unique question IDs
        for question in questions:
            question["question_id"] = generate_question_id()

        return questions

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse OpenAI response as JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating quiz questions: {str(e)}"
        )
