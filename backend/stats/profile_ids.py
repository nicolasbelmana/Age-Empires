def parse_profile_ids(raw_ids):
    profile_ids = []
    for value in raw_ids.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            profile_id = int(value)
        except ValueError as exc:
            raise ValueError(f"ID de perfil inválido: {value!r}.") from exc
        if profile_id <= 0:
            raise ValueError(f"ID de perfil inválido: {value!r}.")
        if profile_id not in profile_ids:
            profile_ids.append(profile_id)
    return tuple(profile_ids)
