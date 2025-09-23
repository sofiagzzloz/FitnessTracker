import asyncio
from typing import List, Dict, Tuple

import httpx

WGER_API = "https://wger.de/api/v2"


def _norm_name(s: str) -> str:
    return " ".join((s or "").strip().split())


def muscles_map_wger() -> Dict[int, str]:
    # WGER muscle ids → simple slugs for your UI
    return {
        2: "chest",
        1: "biceps",
        5: "triceps",
        11: "lats",
        12: "traps",
        8: "abs",
        9: "lower_back",
        10: "quads",
        7: "hams",
        4: "glutes",
        6: "calves",
        3: "front_delts",
        13: "side_delts",
    }


def category_for(name: str) -> str:
    n = (name or "").lower()
    return "cardio" if any(t in n for t in ["run", "treadmill", "bike", "row"]) else "strength"


async def _fetch_exercise_detail(client: httpx.AsyncClient, ex_id: int) -> dict:
    try:
        r = await client.get(f"{WGER_API}/exercise/{ex_id}/")
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return {}


def _score_name(name: str, tokens: List[str]) -> Tuple[int, int, int]:
    """
    Higher is better.
    - matches: how many tokens appear
    - prefix:   whether any token is a prefix of a word (bonus)
    - exact:    exact case-insensitive equality (big bonus)
    """
    n = (name or "").lower()
    words = n.split()
    matches = sum(1 for t in tokens if t in n)
    prefix = 1 if any(any(w.startswith(t) for w in words) for t in tokens) else 0
    exact = 1 if n == " ".join(tokens) else 0
    return (exact, prefix, matches)


async def search_wger(query: str, limit: int = 20) -> List[dict]:
    q = (query or "").strip()
    if not q:
        return []

    headers = {"User-Agent": "fitness-tracker-dev/0.1"}
    limit = max(1, min(limit, 50))
    fetch_size = max(limit * 3, 30)
    tokens = [t for t in q.lower().split() if t]
    mm = muscles_map_wger()

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        t_res = await client.get(
            f"{WGER_API}/exercise-translation/",
            params={"language": 2, "limit": fetch_size, "name__icontains": q},
        )
        t_res.raise_for_status()
        t_data = t_res.json()

        seen: set[int] = set()
        candidates: List[Tuple[int, str]] = []
        for tr in t_data.get("results", []):
            ex_id = tr.get("exercise")
            name = _norm_name(tr.get("name") or "")
            if not ex_id or not name or ex_id in seen:
                continue
            seen.add(ex_id)
            candidates.append((ex_id, name))

        if not candidates:
            return []

        # fetch details in batches (as you already do) ...
        out: List[dict] = []
        batch_size = 10
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            details = await asyncio.gather(
                *(_fetch_exercise_detail(client, ex_id) for ex_id, _ in batch),
                return_exceptions=True
            )
            for (ex_id, name), detail in zip(batch, details):
                if isinstance(detail, Exception):
                    detail = {}

                # NEW: name-token guard (strict)
                nlow = name.lower()
                strict = all(t in nlow for t in tokens) if tokens else True
                if not strict:
                    continue

                primary_ids = detail.get("muscles") or []
                secondary_ids = detail.get("muscles_secondary") or []
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

        # optional: keep your scorer to rank
        if tokens:
            out.sort(key=lambda e: _score_name(e["name"], tokens), reverse=True)
        else:
            out.sort(key=lambda e: e["name"].lower())

        return out[:limit]


async def browse_wger(limit: int = 20, offset: int = 0, muscle: str | None = None) -> List[dict]:
    """
    Browse English exercise names with pagination. Optional 'muscle' filters by
    primary/secondary muscle slugs from the exercise detail endpoint.
    """
    headers = {"User-Agent": "fitness-tracker-dev/0.1"}
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    mm = muscles_map_wger()
    out: List[dict] = []

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        api_offset = 0
        page_size = min(50, max(limit, 20))
        muscle_slug = (muscle or "").strip().lower()
        seen: set[int] = set()
        matches: List[dict] = []

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

            entries: List[Tuple[int, str]] = []
            for tr in results:
                ex_id = tr.get("exercise")
                name = _norm_name(tr.get("name") or "")
                if not ex_id or not name or ex_id in seen:
                    continue
                seen.add(ex_id)
                entries.append((ex_id, name))

            if entries:
                batch_size = 8
                for batch_start in range(0, len(entries), batch_size):
                    batch = entries[batch_start : batch_start + batch_size]
                    details = await asyncio.gather(
                        *(_fetch_exercise_detail(client, ex_id) for ex_id, _ in batch),
                        return_exceptions=True,
                    )
                    for (ex_id, name), detail in zip(batch, details):
                        if isinstance(detail, Exception):
                            detail = {}
                        primary_ids = detail.get("muscles") or []
                        secondary_ids = detail.get("muscles_secondary") or []
                        muscles = {
                            "primary": [mm[i] for i in primary_ids if i in mm],
                            "secondary": [mm[i] for i in secondary_ids if i in mm],
                        }
                        if muscle_slug:
                            slug_hits = set(muscles["primary"]) | set(muscles["secondary"])
                            if muscle_slug not in slug_hits:
                                continue
                        cat = category_for(name)
                        matches.append(
                            {
                                "source": "wger",
                                "source_ref": str(ex_id),
                                "name": name,
                                "category": cat,
                                "equipment": None,
                                "default_unit": "kg" if cat == "strength" else "min",
                                "muscles": muscles,
                            }
                        )
                        if len(matches) >= offset + limit:
                            break
                    if len(matches) >= offset + limit:
                        break

            api_offset += page_size

        out = matches[offset : offset + limit]

    return out