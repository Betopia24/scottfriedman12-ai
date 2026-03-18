# app/services/openai_service.py
from openai import AsyncOpenAI
from app.database.database import settings


client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_course_name(
    course_name: str,
    subject: str,
    target_grade_level: str,
    course_length: str,
    semester_count: int,
    total_modules: int,
    estimated_duration_min_per_class: int,
) -> str:
    """
    Uses OpenAI GPT-4.1 to generate a compelling, structured course title
    based on the provided course details.
    """

    prompt = f"""You are an expert academic curriculum designer. 
Based on the following course details, generate one compelling, clear, and professional course title.

Course Details:
- Provided Course Name: {course_name}
- Subject: {subject}
- Target Grade / Level: {target_grade_level}
- Course Length: {course_length}
- Semester Count: {semester_count}
- Total Modules: {total_modules}
- Estimated Duration: {estimated_duration_min_per_class} minutes per class

Rules:
- The title must be engaging and descriptive.
- Keep it under 12 words.
- Do NOT include quotes, explanations, or extra text — only return the course title itself.
"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # Faster model
        messages=[
            {
                "role": "system",
                "content": "You are an expert academic curriculum designer who creates clear, engaging course titles.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=60,
        temperature=0.1,
    )

    generated_name = response.choices[0].message.content.strip()
    return generated_name