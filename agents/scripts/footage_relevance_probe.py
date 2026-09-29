"""P4 follow-up probe: is the relevance score doing any work?

Two things looked wrong on inspection and neither is provable by reading:

1. _search_pexels_uncached() keeps id/url/width/height/duration/fps/size/source/query
   and DROPS Pexels' own video title. So nothing downstream can know what a clip
   depicts, and neither can this audit.
2. _score_stock_relevance(candidate, keyword) scores
       len(keyword_words & candidate["query"].split()) / len(keyword_words)
   but every candidate from one search carries candidate["query"] == the keyword we
   just sent. That is a tautology: it should return ~1.0 for all of them and rank
   nothing. If so, the winner is decided by Pexels' own ordering plus jitter, and
   the "relevance" number is decorative.

This fetches the same queries through the real module, then separately asks Pexels
what the clips are actually called, so relevance can be judged as text instead of
inferred from pixels.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")
import requests

from utils.stock_video import (
    PEXELS_API_KEY, _search_providers, _score_stock_relevance,
    _repeat_penalty, _stable_jitter,
)
from scripts.footage_audit import SCENES, OUT_DIR
from utils.scene_parser import clean_scene_keywords, _apply_category_style

KEY = PEXELS_API_KEY


def pexels_titles(query: str, per_page: int = 5) -> list[tuple[int, str, str]]:
    """What does Pexels actually think this query matched? Not in stock_video's
    retained fields, so ask the API directly."""
    if not KEY:
        return []
    r = requests.get("https://api.pexels.com/videos/search",
                     headers={"Authorization": KEY},
                     params={"query": query, "per_page": per_page}, timeout=20)
    if r.status_code != 200:
        return []
    out = []
    for v in r.json().get("videos", []):
        src = v.get("image", "") or ""
        out.append((v.get("id"), v.get("user", {}).get("name", ""), src))
    return out


def main() -> int:
    findings = []
    for i, spec in enumerate(SCENES):
        scene = {"keyword": spec["title"], "description": spec["narration"],
                 "asset_keywords": [spec["title"]], "render_type": "stock",
                 "asset_type": "STOCK_FOOTAGE"}
        scene = _apply_category_style([scene], spec["category"])[0]
        kw_list = clean_scene_keywords(scene["asset_keywords"]) or ["technology"]
        joined = ", ".join(kw_list)

        cands = _search_providers([joined], "landscape")
        if not cands:
            findings.append({"scene": i, "note": "no candidates for join"})
            continue

        # Exactly the sort the pipeline performs (minus the same-query collapse).
        scored = []
        for c in cands:
            cid = f"{c['source']}_{c['id']}"
            s = _score_stock_relevance(c, joined, spec["narration"])
            s = s - _repeat_penalty(cid) + _stable_jitter(f"audit{i}", i, cid)
            scored.append((s, cid))
        scored.sort(reverse=True)

        raw = [_score_stock_relevance(c, joined, spec["narration"]) for c in cands]
        titles = pexels_titles(joined)
        # Keys MUST be str: cid.split() yields a str id, and the int id from the
        # JSON would never match it. Silently printed "?" for every clip when I
        # got this wrong.
        by_id = {str(tid): (user, url) for tid, user, url in titles}

        # The decisive measurement, and it needs no vision: does the comma-join
        # change WHICH clips we get, compared to a focused query?
        #   join  = ", ".join(kw_list)   <- what asset_router:176 actually sends
        #   focus = the scene's own title words
        # If join == focus, the extra keywords are decoration. If they differ, the
        # join is actively choosing different footage, which has to be justified.
        def _ids(q):
            if not KEY:
                return set()
            r = requests.get("https://api.pexels.com/videos/search",
                             headers={"Authorization": KEY},
                             params={"query": q, "per_page": 5}, timeout=20)
            return {str(v.get("id")) for v in r.json().get("videos", [])} if r.status_code == 200 else set()

        id_join = _ids(joined)
        id_focus = _ids(spec["title"])
        id_cat = _ids(" ".join(kw_list[1:]))

        def _jacc(a, b):
            return round(len(a & b) / len(a | b), 3) if (a or b) else None

        findings.append({
            "scene": i,
            "category": spec["category"],
            "title": spec["title"],
            "joined_query": joined,
            "candidates": len(cands),
            "relevance_scores": [round(s, 4) for s in raw],
            "relevance_spread": round(max(raw) - min(raw), 4) if raw else None,
            "pipeline_picks": scored[0][1],
            "pipeline_top_3": [c for _, c in scored[:3]],
            "clip_titles": {str(tid): {"user": u, "image": im} for tid, (u, im) in by_id.items()},
            "ids_join": sorted(id_join),
            "ids_focus": sorted(id_focus),
            "ids_category": sorted(id_cat),
            "jaccard_join_vs_focus": _jacc(id_join, id_focus),
            "jaccard_join_vs_category": _jacc(id_join, id_cat),
            "focus_ids_missing_from_join": sorted(id_focus - id_join),
        })
        print(f"\n[{i}] {spec['category']}  candidates={len(cands)}")
        print(f"    relevance spread = {findings[-1]['relevance_spread']}  "
              f"scores={findings[-1]['relevance_scores']}")
        print(f"    join vs focus  J={findings[-1]['jaccard_join_vs_focus']}  "
              f"focus-only={len(id_focus - id_join)}/{len(id_focus)}")
        print(f"    join vs catkw  J={findings[-1]['jaccard_join_vs_category']}")
        for s, cid in scored[:3]:
            tid = cid.split("_", 1)[1]
            u, im = by_id.get(tid, ("?", "?"))
            print(f"    pick {cid:<22} score={s:+.4f}  by={u}")

    (OUT_DIR / "relevance_probe.json").write_text(json.dumps(findings, indent=2))
    spreads = [f.get("relevance_spread") for f in findings if f.get("relevance_spread") is not None]
    if spreads:
        print(f"\n[probe] relevance spread across scenes: min={min(spreads)} max={max(spreads)}")
    print(f"[probe] wrote {OUT_DIR / 'relevance_probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
