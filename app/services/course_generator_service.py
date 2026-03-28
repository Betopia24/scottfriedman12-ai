# app/services/course_generator_service.py
import json
from openai import AsyncOpenAI
from fastapi import HTTPException, status
from app.database.database import settings
from app.services.embedding_service import retrieve_context


async def generate_single_module(course_data: dict, module_number: int) -> dict:

    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured in .env",
        )

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    total_modules = course_data.get("total_modules", 5)
    course_name = course_data.get("generated_course_name", course_data.get("course_name", ""))
    subject = course_data.get("subject", "")
    grade_level = course_data.get("target_grade_level", "")

    user_instration = course_data.get("user_instration")
    knowledge_bases = course_data.get("knowledge_bases", [])
    rag_query = f"Module {module_number} content for {course_name} ({subject}) for {grade_level}"
    rag_context = await retrieve_context(
        query=rag_query,
        knowledge_bases=knowledge_bases,
        top_k=8,
        max_chars=5000,
    )


    instruction_block = f"\nUser Instruction:\n{user_instration}\n" if user_instration else ""
    context_block = f"\nReference Context (from PDFs):\n{rag_context}\n" if rag_context else ""

    prompt = f"""You are an expert academic curriculum designer.

Create module {module_number} of {total_modules} for: {course_name} ({subject})
Target Level: {grade_level}
{instruction_block}{context_block}
Generate a module with the following JSON structure:

{{
  "module_number": {module_number},
  "title": "<concise, descriptive title for this module (4-8 words)>",
  "introduction": "<4-6 sentence introduction to the entire module explaining what it covers, why it's important, and how it fits into the course>",
  "resources": [
    {{
      "title": "<resource title (include author or publisher where applicable)>",
      "type": "<one of: book | article | website | video>",
      "description": "<2-3 sentences explaining what this resource covers and how it supports the module>"
    }}
  ],
  "study_topics": [
    {{
      "topic_name": "<clear, descriptive topic name>",
      "topic_wise_study_data": {{
        "summary": "<2-3 sentence introduction to the topic and its importance>",
        "detailed_explanation": "<8-12 sentence in-depth explanation covering: core concepts and definitions, underlying principles and theory, step-by-step breakdown of how it works, common misconceptions, real-world examples and practical applications, and connections to other topics in the module>",
        "resources": [
          {{
            "title": "<resource title (include author or publisher where applicable)>",
            "type": "<one of: book | article | website>",
            "description": "<2-3 sentences explaining what this resource covers and why it is relevant to this specific topic>"
          }}
        ]
      }}
    }}
  ]
}}

REQUIREMENTS:
- Create a clear, descriptive title for this module (4-8 words)
- Include 4-5 study topics for this module
- Each topic MUST have: topic_name, summary, detailed_explanation, and resources
- The top-level "resources" array should contain 2-4 general module references (textbooks, authoritative websites)
- Each topic's "resources" array should contain 1-3 references directly relevant to that specific topic
- Resources MUST be real, well-known references (e.g. Khan Academy, standard textbooks, Wikipedia, academic publishers)
- Content should be appropriate for {grade_level} and relevant to {subject}
- Return ONLY the JSON object
- No markdown, no code fences
"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # Much faster than gpt-4
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert curriculum designer. "
                    "Respond with a valid JSON object for a single module. "
                    "No markdown, no explanations, no code fences - only the JSON object."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    try:
        module = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from GPT: {e}. Raw response: {raw[:500]}")

    # Ensure it's a dict with the expected structure
    if not isinstance(module, dict):
        raise ValueError(f"Expected module dict, got {type(module)}")
    
    if "module_number" not in module:
        module["module_number"] = module_number
    
    print(f"✅ Successfully generated module {module_number}")
    return module