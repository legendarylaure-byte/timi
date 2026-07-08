# Fix: compliance_check `'str' object has no attribute 'get'`

## Problem
Both short and long video pipelines crash at `compliance_check` with `'str' object has no attribute 'get'` because `issues` list items are assumed to be `dict` but could contain a `str`, causing `.get()` calls on lines 822-824 and 1149-1151 to fail.

## Changes

### 1. `agents/main.py` — Short pipeline (line ~822)
Replace:
```python
                for issue in issues[:3]:
                    log_event("COMPLIANCE", f"  [{issue['severity']}] {issue.get('detail', '')[:100]}")
                if any(i.get("severity") == "high" for i in issues):
```
With:
```python
                for issue in issues[:3]:
                    if isinstance(issue, dict):
                        log_event("COMPLIANCE", f"  [{issue.get('severity', '?')}] {issue.get('detail', '')[:100]}")
                if any(isinstance(i, dict) and i.get("severity") == "high" for i in issues):
```

### 2. `agents/main.py` — Long pipeline (line ~1149)
Same replacement (identical code, use `replaceAll`).

### 3. Deploy
- Build dashboard: `npm run build`
- Deploy: `npx vercel --prod`
- Re-alias: `npx vercel alias set timi-dashboard.vercel.app timi.vyomai.cloud`
