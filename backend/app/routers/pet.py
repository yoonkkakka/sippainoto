from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.schemas.pet import PetState
from app.services.pet import get_or_create_pet, pat_pet, to_pet_state

router = APIRouter(prefix="/pet", tags=["pet"])


@router.get("", response_model=PetState)
async def get_pet(current_user: dict = Depends(get_current_user)) -> dict:
    client = current_user["client"]
    pet = get_or_create_pet(client, current_user["id"])
    return to_pet_state(pet)


@router.post("/pat", response_model=PetState)
async def pat(current_user: dict = Depends(get_current_user)) -> dict:
    client = current_user["client"]
    pet, already_patted = pat_pet(client, current_user["id"])
    if already_patted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="오늘은 이미 쓰다듬었어요. 내일 또 와주세요.",
        )
    return to_pet_state(pet)
