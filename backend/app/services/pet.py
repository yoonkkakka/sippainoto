from datetime import date, datetime, timezone

EXP_PER_LEVEL = 100
EXP_PER_ENTRY = 20
AFFECTION_PER_ENTRY = 8
AFFECTION_PER_PAT = 5
AFFECTION_DECAY_PER_DAY = 5
MAX_AFFECTION = 100


def _mood_from_affection(affection: int) -> str:
    if affection >= 80:
        return "happy"
    if affection >= 50:
        return "normal"
    if affection >= 20:
        return "sad"
    return "angry"


def _apply_decay(pet: dict) -> dict:
    last = datetime.fromisoformat(pet["last_interaction_at"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    days_idle = max((datetime.now(timezone.utc) - last).days, 0)
    if days_idle <= 0:
        return pet
    decayed = max(pet["affection"] - AFFECTION_DECAY_PER_DAY * days_idle, 0)
    pet["affection"] = decayed
    return pet


def get_or_create_pet(client, user_id: str) -> dict:
    existing = client.table("pet_state").select("*").eq("user_id", user_id).limit(1).execute()
    if existing.data:
        pet = existing.data[0]
    else:
        created = (
            client.table("pet_state")
            .insert({"user_id": user_id})
            .execute()
        )
        pet = created.data[0]

    pet = _apply_decay(pet)
    client.table("pet_state").update({"affection": pet["affection"]}).eq("user_id", user_id).execute()
    return pet


def to_pet_state(pet: dict) -> dict:
    return {
        "level": pet["level"],
        "exp": pet["exp"],
        "exp_to_next": EXP_PER_LEVEL - pet["exp"],
        "affection": pet["affection"],
        "mood": _mood_from_affection(pet["affection"]),
        "last_interaction_at": pet["last_interaction_at"],
    }


def add_exp(client, user_id: str, amount: int) -> dict:
    pet = get_or_create_pet(client, user_id)

    level = pet["level"]
    exp = pet["exp"] + amount
    while exp >= EXP_PER_LEVEL:
        exp -= EXP_PER_LEVEL
        level += 1

    affection = min(pet["affection"] + AFFECTION_PER_ENTRY, MAX_AFFECTION)

    updated = (
        client.table("pet_state")
        .update(
            {
                "level": level,
                "exp": exp,
                "affection": affection,
                "last_interaction_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("user_id", user_id)
        .execute()
    )
    return updated.data[0]


def pat_pet(client, user_id: str) -> tuple[dict, bool]:
    """쓰다듬기: 하루 한 번만 애정도 상승. (상태, 오늘 이미 쓰다듬었는지) 반환."""
    pet = get_or_create_pet(client, user_id)
    today = date.today().isoformat()
    last_patted = pet.get("last_patted_at")
    already_patted = bool(last_patted) and last_patted[:10] == today

    if already_patted:
        return pet, True

    affection = min(pet["affection"] + AFFECTION_PER_PAT, MAX_AFFECTION)
    updated = (
        client.table("pet_state")
        .update(
            {
                "affection": affection,
                "last_patted_at": datetime.now(timezone.utc).isoformat(),
                "last_interaction_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("user_id", user_id)
        .execute()
    )
    return updated.data[0], False
