import httpx

WGER_API = "https://wger.de/api/v2"

def _norm_name(s: str) -> str:
    return " ".join((s or "").strip().split())

def muscles_map_wger() -> dict[int, str]:
    return {
        2: "chest", 1: "biceps", 5: "triceps", 11: "lats", 12: "traps",
        8: "abs", 9: "lower_back", 10: "quads", 7: "hams", 4: "glutes",
        6: "calves", 3: "front_delts", 13: "side_delts",
    }

def category_for(name: str) -> str:
    n = (name or "").lower()
    return "cardio" if any(t in n for t in ["run","treadmill","bike","row"]) else "strength"

async def search_wger(query: str, limit: int = 20) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []

    headers = {"User-Agent": "fitness-tracker-dev/0.1"}
    limit = max(1, min(limit, 50))
    mm = muscles_map_wger()
    out: list[dict] = []

    tokens = [t for t in q.lower().split() if t]

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # 1) English names
        t_res = await client.get(
            f"{WGER_API}/exercise-translation/",
            params={"language": 2, "limit": limit, "name__icontains": q},
        )
        t_res.raise_for_status()
        t_data = t_res.json()

        # build picks
        picks_strict: list[tuple[int, str]] = []
        picks_loose: list[tuple[int, str]] = []
        seen: set[int] = set()

        for tr in t_data.get("results", []):
            ex_id = tr.get("exercise")
            name = _norm_name(tr.get("name") or "")
            if not ex_id or not name or ex_id in seen:
                continue
            nlow = name.lower()
            every = all(t in nlow for t in tokens) if tokens else True
            anyy  = any(t in nlow for t in tokens) if tokens else True
            if every:
                picks_strict.append((ex_id, name))
                seen.add(ex_id)
            elif anyy:
                picks_loose.append((ex_id, name))
                seen.add(ex_id)

        picks = picks_strict or picks_loose  # prefer strict; fallback to loose

        # 2) enrich with /exercise/<id>
        for ex_id, name in picks:
            try:
                e_res = await client.get(f"{WGER_API}/exercise/{ex_id}/")
                e_res.raise_for_status()
                e = e_res.json()
                primary_ids = e.get("muscles") or []
                secondary_ids = e.get("muscles_secondary") or []
            except httpx.HTTPError:
                primary_ids, secondary_ids = [], []

            muscles = {
                "primary": [mm[i] for i in primary_ids if i in mm],
                "secondary": [mm[i] for i in secondary_ids if i in mm],
            }
            cat = category_for(name)
            out.append({
                "source": "wger",
                "source_ref": str(ex_id),
                "name": name,
                "category": cat,
                "equipment": None,
                "default_unit": "kg" if cat == "strength" else "min",
                "muscles": muscles,
            })

    return out

async def browse_wger(limit: int = 20, offset: int = 0, muscle: str | None = None) -> list[dict]:
    """
    Browse English exercise names with pagination. Optional 'muscle' filters by
    primary/secondary muscle slugs from the exercise detail endpoint.
    """
    headers = {"User-Agent": "fitness-tracker-dev/0.1"}
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    mm = muscles_map_wger()
    out: list[dict] = []

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # keep fetching pages until we have enough matches or run out
        api_offset = 0
        page_size = min(50, max(limit, 20))
        muscle_slug = (muscle or "").strip().lower()
        seen: set[int] = set()
        matches: list[dict] = []

        while len(matches) < offset + limit:
            t_res = await client.get(
                f"{WGER_API}/exercise-translation/",
                params={"language": 2, "limit": page_size, "offset": api_offset},
            )
            t_res.raise_for_status()
            t_data = t_res.json()

            results = t_data.get("results", [])
            if not results:
                break

            for tr in results:
                ex_id = tr.get("exercise")
                name = _norm_name(tr.get("name") or "")
                if not ex_id or not name or ex_id in seen:
                    continue

                seen.add(ex_id)

                primary_ids: list[int] = []
                secondary_ids: list[int] = []
                try:
                    e_res = await client.get(f"{WGER_API}/exercise/{ex_id}/")
                    e_res.raise_for_status()
                    e = e_res.json()
                    primary_ids = e.get("muscles") or []
                    secondary_ids = e.get("muscles_secondary") or []
                except httpx.HTTPError:
                    pass

                muscles = {
                    "primary": [mm[i] for i in primary_ids if i in mm],
                    "secondary": [mm[i] for i in secondary_ids if i in mm],
                }

                if muscle_slug:
                    slug_hits = set(muscles["primary"]) | set(muscles["secondary"])
                    if muscle_slug not in slug_hits:
                        continue

                cat = category_for(name)
                matches.append({
                    "source": "wger",
                    "source_ref": str(ex_id),
                    "name": name,
                    "category": cat,
                    "equipment": None,
                    "default_unit": "kg" if cat == "strength" else "min",
                    "muscles": muscles,
                })

                if len(matches) >= offset + limit:
                    break

            api_offset += page_size

        out = matches[offset:offset + limit]

    return out
