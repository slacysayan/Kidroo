# Skill — Composio (YouTube OAuth + uploads)

Read this when you are connecting a new YouTube channel, debugging OAuth, or calling a new Composio action.

## Prerequisites

- `COMPOSIO_API_KEY` in `.env`.
- Composio CLI installed (`composio --version`).

## Connecting a new YouTube channel

```bash
composio connections create --toolkit YOUTUBE --user-id <entity_name>
```

- `<entity_name>` is your human-readable channel alias (e.g. `finance_daily`, `tech_weekly`). It becomes the `entity_id` used in every subsequent action call.
- The CLI opens an OAuth URL in your browser. Log into the Google account that owns the target YouTube channel and consent.
- On success, insert the channel into Supabase:
  ```sql
  insert into public.channels (user_id, name, composio_entity_id, connected)
  values (auth.uid(), 'Finance Daily', 'finance_daily', true);
  ```

## Using the YouTube actions from Python

```python
from composio import Composio
composio = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

resp = composio.actions.execute(
    action="YOUTUBE_UPLOAD_VIDEO",
    entity_id="finance_daily",       # <-- the key that routes to the right channel
    params={...},
)
```

Full parameter reference lives in `docs/INTEGRATIONS.md#composio--youtube`.

## Debugging

### "No connection found for entity"

You referenced an entity that hasn't completed OAuth. Run `composio connections list --user-id <entity>` to verify; re-run `composio connections create` if absent.

### "Upload succeeded but video disappeared in YouTube Studio"

This is Composio bug [#2954](https://github.com/ComposioHQ/composio/issues/2954) — file bytes never transferred. The runtime's upload agent has a 60-second verification poll after `YOUTUBE_UPLOAD_VIDEO` returns. If the poll fails, the agent retries up to 3 times. Do not disable the verification.

### "Quota exceeded"

YouTube Data API quota is per **Google Cloud project**, not per channel. The shared Composio-managed OAuth app has strict limits. To raise quota:

1. Create a GCP project + OAuth client per the Composio docs: https://composio.dev/auth/googleapps
2. Upload the OAuth client JSON to Composio.
3. The entity now uses your dedicated project's quota.

### `publishAt` scheduling

Current strategy (safe across Composio versions):
1. Upload with `privacyStatus='private'`.
2. Follow up with `YOUTUBE_UPDATE_VIDEO` passing `{"status": {"privacyStatus": "private", "publishAt": "<ISO-8601 UTC>"}}`.

YouTube auto-flips privacy to public at `publishAt`. Do not set `publishAt` directly in the upload params until Phase 2 confirms the toolkit version exposes it — even then, keep the two-call fallback.

## Common failures

| Symptom | Fix |
|---|---|
| OAuth consent screen says "unverified app" | Expected in dev. Click "Advanced" → "Continue" — or set up your own OAuth app to avoid the warning |
| Upload returns `uploadStatus: "processed"` but video is rejected | Usually Content ID / copyright. Check YouTube Studio for the claim. Not a Composio bug. |
| `executeAction` returns 404 for a slug | Toolkit was updated; slug changed. Check the Composio docs or `composio.actions.list(toolkit="YOUTUBE")` |

## Related files

- `docs/INTEGRATIONS.md` — exact call signatures
- `agents/upload/skills/composio_youtube.py` — upload skill (Phase 2)
- `.agents/skills/security/SKILL.md` — ToS / Content ID guardrails
