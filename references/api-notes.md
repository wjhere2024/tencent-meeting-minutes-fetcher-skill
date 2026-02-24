# API Reference Notes

Observed working flow for Tencent Meeting share pages:

1. Resolve `share_id` from page HTML (`id=<uuid>` in embedded data).
2. POST `/wemeet-tapi/v2/meetlog/public/detail/common-record-info`
   - request includes `sharing_id`, `pwd`, `short_url_code`
   - response includes `meeting_info.meeting_id` and `recordings[].id`
3. GET `/wemeet-cloudrecording-webapi/v1/minutes/detail`
   - request includes `id` (share_id), `pwd`, `meeting_id`, `recording_id`
   - response includes `minutes.paragraphs[]` and optional `next_pid`

Known URLs:
- https://meeting.tencent.com/wemeet-tapi/v2/meetlog/public/detail/common-record-info
- https://meeting.tencent.com/wemeet-cloudrecording-webapi/v1/minutes/detail

Expected output structure:
- JSON: full response transformed to include share context + paragraphs
- TXT: timestamp + speaker + concatenated sentence text
