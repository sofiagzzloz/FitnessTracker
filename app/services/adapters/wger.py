import asyncio
import re
import unicodedata
from typing import List, Dict, Tuple


import httpx


WGER_API = "https://wger.de/api/v2"






# Normalization & token helpers
_PUNCT_RE = re.compile(r"[^\w\s]+")
_WS_RE = re.compile(r"\s+")




def _strip_accents(s: str) -> str:
   s = unicodedata.normalize("NFKD", s)
   return "".join(c for c in s if not unicodedata.combining(c))




def _norm(s: str) -> str:
   """lowercase, strip accents, remove punctuation, collapse spaces."""
   if not s:
       return ""
   s = _strip_accents(s).lower()
   s = _PUNCT_RE.sub(" ", s)
   s = _WS_RE.sub(" ", s).strip()
   return s




def _singularize_token(t: str) -> str:
   """Very naive singularization to make 'squats' → 'squat', 'presses' → 'press'."""
   if len(t) > 3 and re.search(r"[^aeiou]es$", t):
       return t[:-2]
   if len(t) > 3 and t.endswith("s"):
       return t[:-1]
   return t




def _tokens(s: str) -> List[str]:
   return [_singularize_token(t) for t in _norm(s).split() if t]




def _norm_name(s: str) -> str:
   """Preserve your original whitespace-collapse utility where needed."""
   return " ".join((s or "").strip().split())






# Domain helpers
def muscles_map_wger() -> Dict[int, str]:
   # WGER muscle ids
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




# HTTP helpers
async def _fetch_exercise_detail(client: httpx.AsyncClient, ex_id: int) -> dict:
   try:
       r = await client.get(f"{WGER_API}/exercise/{ex_id}/")
       r.raise_for_status()
       return r.json()
   except httpx.HTTPError:
       return {}


async def _fetch_json(client: httpx.AsyncClient, url: str, params: dict) -> dict:
   r = await client.get(url, params=params)
   r.raise_for_status()
   return r.json()


def _cand_from_translation(t_data: dict) -> list[tuple[int, str]]:
   seen: set[int] = set()
   out: list[tuple[int, str]] = []
   for tr in t_data.get("results", []) or []:
       ex_id = tr.get("exercise")
       name = _norm_name(tr.get("name") or "")
       if not ex_id or not name or ex_id in seen:
           continue
       seen.add(ex_id)
       out.append((ex_id, name))
   return out




# Scoring
def _score_name(name: str, q_tokens: List[str]) -> Tuple[int, int, int, int]:
   """
   Higher is better:
     (exact_phrase, exact_word_hits, prefix_hits, -name_len)
   """
   n_norm = _norm(name)
   if not n_norm:
       return (0, 0, 0, 0)


   words = n_norm.split()
   exact_word_hits = sum(1 for t in q_tokens if t in words)
   prefix_hits = sum(1 for t in q_tokens if any(w.startswith(t) for w in words))
   exact_phrase = 1 if n_norm == " ".join(q_tokens) else 0
   return (exact_phrase, exact_word_hits, prefix_hits, -len(n_norm))




# Public: Search (strict AND)
async def search_wger(query: str, limit: int = 20) -> List[dict]:
   """
   Strategy:
     - Page through /exercise-translation/?language=2 (no server-side filters)
     - Locally normalize + strict token-AND on the English name
     - For matched exercise ids, fetch /exercise/<id>/ to get muscles (stable)
     - Rank deterministically and cap to `limit`
   """
   q_raw = (query or "").strip()
   if not q_raw:
       return []


   headers = {"User-Agent": "fitness-tracker-dev/0.1"}
   limit = max(1, min(limit, 50))
   soft_cap = max(limit * 5, 100)
   q_tokens = _tokens(q_raw)
   if not q_tokens:
       return []


   mm = muscles_map_wger()


   async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
       # Sweep translations and filter locally by strict AND
       page_size = 100
       max_pages = 20
       offset = 0
       cand: list[tuple[int, str]] = []


       for _ in range(max_pages):
           try:
               t_data = await _fetch_json(
                   client,
                   f"{WGER_API}/exercise-translation/",
                   {"language": 2, "limit": page_size, "offset": offset},
               )
           except httpx.HTTPError:
               break


           results = t_data.get("results", []) or []
           if not results:
               break


           for tr in results:
               ex_id = tr.get("exercise")
               name = _norm_name(tr.get("name") or "")
               if not ex_id or not name:
                   continue
               if all(t in _norm(name) for t in q_tokens):
                   cand.append((ex_id, name))
                   if len(cand) >= soft_cap:
                       break
           if len(cand) >= soft_cap:
               break
           offset += page_size


       if not cand:
           return []


       # Dedup by id, keep first name
       seen_ids: set[int] = set()
       unique_cand: list[tuple[int, str]] = []
       for ex_id, name in cand:
           if ex_id in seen_ids:
               continue
           seen_ids.add(ex_id)
           unique_cand.append((ex_id, name))


       # Enrich via /exercise/<id>/ (stable)
       out: List[dict] = []
       batch_size = 10
       for i in range(0, len(unique_cand), batch_size):
           batch = unique_cand[i : i + batch_size]
           details = await asyncio.gather(
               *(_fetch_exercise_detail(client, ex_id) for ex_id, _ in batch),
               return_exceptions=True,
           )
           for (ex_id, name), detail in zip(batch, details):
               if isinstance(detail, Exception) or not isinstance(detail, dict):
                   detail = {}


               primary_ids = detail.get("muscles") or []
               secondary_ids = detail.get("muscles_secondary") or []
               muscles = {
                   "primary": [mm[i] for i in primary_ids if i in mm],
                   "secondary": [mm[i] for i in secondary_ids if i in mm],
               }
               cat = category_for(name)
               out.append(
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
           if len(out) >= soft_cap:
               break


       # Rank and cap
       out.sort(key=lambda e: _score_name(e["name"], q_tokens), reverse=True)
       return out[:limit]




# Public: Browse
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