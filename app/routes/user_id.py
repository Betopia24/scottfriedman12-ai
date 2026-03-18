#app/routes/user_id.py
import uuid
import random
import string
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.database import get_db
from app.models.user_id import UserIdModel
from app.schemas.schemas import GenerateUserIdResponse, AllUserIdsResponse, UserIdResponse

router = APIRouter(
    prefix="/user-id",
    tags=["User ID"],
)

COLLECTION_NAME = "User_id table"


def generate_unique_user_id() -> str:
    """
    Generates a globally unique User ID in the format: USR-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
    Uses a full UUID4 — statistically impossible to collide (2^122 combinations).
    """
    return f"USR-{uuid.uuid4()}"


@router.post(
    "/generate",
    response_model=GenerateUserIdResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new unique User ID",
    description="Generates a globally unique User ID using UUID4, stores it in the 'User_id table' collection, and returns it.",
)
async def generate_user_id():
    db = get_db()
    collection = db[COLLECTION_NAME]

    # UUID4 is astronomically unique — no collision loop needed
    new_user_id = generate_unique_user_id()

    user_record = UserIdModel(user_id=new_user_id)
    doc = user_record.model_dump()
    result = await collection.insert_one(doc)

    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save User ID to database.",
        )

    return GenerateUserIdResponse(
        success=True,
        message="User ID generated and saved successfully.",
        data=UserIdResponse(**doc),
    )


@router.get(
    "/all",
    response_model=AllUserIdsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve all generated User IDs",
    description="Returns all User IDs stored in the 'User_id table' collection.",
)
async def get_all_user_ids():
    db = get_db()
    collection = db[COLLECTION_NAME]

    cursor = collection.find({}, {"_id": 0})
    records = await cursor.to_list(length=None)

    return AllUserIdsResponse(
        success=True,
        total=len(records),
        data=[UserIdResponse(**r) for r in records],
    )


@router.get(
    "/{user_id}",
    response_model=GenerateUserIdResponse,
    status_code=status.HTTP_200_OK,
    summary="Look up a specific User ID",
    description="Finds and returns a specific User ID from the 'User_id table' collection.",
)
async def get_user_id(user_id: str):
    db = get_db()
    collection = db[COLLECTION_NAME]

    record = await collection.find_one({"user_id": user_id.upper()}, {"_id": 0})
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User ID '{user_id}' not found.",
        )

    return GenerateUserIdResponse(
        success=True,
        message="User ID found.",
        data=UserIdResponse(**record),
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a specific User ID",
    description="Deletes a User ID from the 'User_id table' collection.",
)
async def delete_user_id(user_id: str):
    db = get_db()
    collection = db[COLLECTION_NAME]

    result = await collection.delete_one({"user_id": user_id.upper()})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User ID '{user_id}' not found.",
        )

    return {"success": True, "message": f"User ID '{user_id}' deleted successfully."}