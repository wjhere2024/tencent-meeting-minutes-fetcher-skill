---
name: tencent-meeting-minutes-fetcher
description: Fetch Tencent Meeting shared recording transcript/minutes from a share URL and password, then export JSON/TXT. This skill should be used when users ask to extract 腾讯会议 文稿/转写/纪要 from a meeting share link.
---

# Tencent Meeting Minutes Fetcher

Use this skill to extract transcript/minutes text from Tencent Meeting shared recording links.

## When To Use

Use when the user provides a Tencent Meeting recording share link (for example `meeting.tencent.com/crm/...`, `meeting.tencent.com/cw/...`, or `meeting-record/shares?id=...`) and asks to get:
- 文稿
- 转写
- 纪要原文
- transcript text export

## Workflow

1. Validate required inputs:
- share URL
- access password

2. Run the bundled script:

```powershell
python C:\Users\lenovo\.codex\skills\tencent-meeting-minutes-fetcher\scripts\fetch_minutes.py \
  --url "<share_url>" \
  --password "<password>" \
  --outdir "<output_dir>" \
  --prefix "minutes"
```

3. Return output file paths:
- `<output_dir>/minutes.json`
- `<output_dir>/minutes.txt`

4. If user asks for summary, summarize from exported text.

## Script Behavior

The script performs this API chain:
1. Load share page HTML to resolve `share_id`.
2. Call `common-record-info` to resolve `meeting_id` and `recording_id`.
3. Call `minutes/detail` (paginated) to fetch all paragraphs.
4. Export structured JSON and readable TXT.

## Troubleshooting

- If response code indicates permission or password errors:
  - verify password
  - verify link is still valid and not expired
- If no transcript is returned:
  - recording may not have minutes/transcription generated
  - retry later if minutes are still processing
- If anti-bot controls change endpoint behavior:
  - capture latest request pattern in browser network tab and adjust script fields

## Notes

- This skill uses public web endpoints backing the share page.
- Endpoint behavior may change; keep the script updated when Tencent updates web client behavior.
