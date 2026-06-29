# Cloud Video Manager Migration Reference

Use this reference for 云视频管家 API migration result verification.

## Open API Result Sources

Relevant endpoints from the local API document:

- Auth: `/openapi/auth/access_token`
- Users: `/openapi/account/list`
- Teams: `/openapi/team/list`
- Groups: `/openapi/group/list`
- Video categories: `/openapi/video/type/list`
- Video status: `/openapi/video/state/list`
- Video labels: `/openapi/video/label/list`
- Video import: `/openapi/video/import`
- Video import result: `/openapi/video/import/query`
- Video list: `/openapi/video/list`
- Finished video to material relation: `/openapi/video/relation/material/list`
- Third-party material relation: `/openapi/video/relation/third/material/list`

## Core API Fields

`/openapi/video/list` can verify:

- `id` / video ID
- `name`
- `videoType`: `0` finished video, `1` material, `2` third party, `3` image, `4` copywriting
- `accountKey`, `accountName`
- `oneLevelVideoType`, `twoLevelVideoType`
- `videoLabels`
- `videoState`
- `state`: transcoding state, `0~1` pending, `2` success, `3~7` failed, `8/10` transcoding
- `duration`: seconds
- `fileSize`: bytes
- `coverUrl`
- `videoUrl`
- `desc`, `videoRemark`
- `createTime`, `shootTime`, `lastModifyTime`

`/openapi/video/relation/material/list` can verify:

- `relationId`
- `videoId`
- `materialId`
- `materialProjectTracksList`
- `start`: microseconds
- `duration`: microseconds
- `attribute`: `0` normal, `1` mute, `2` hide, `3` mute+hide, `4` lock, `5` lock+mute, `6` lock+hide, `7` lock+mute+hide
- `flag`: cover flag
- `tracksIndex`
- `projectId`
- `accountKey`

`/openapi/video/import/query` can verify:

- `videoId`
- `videoName`
- `status`: `0` pending, `3` file downloading, `10` success, `20` failed
- `msg`

## Verification Notes

- Main result verification should not test API add/edit/list behavior as product functionality. Use APIs only as target result query channels.
- Use target database for fields not exposed by API, such as mapping tables, default collection, category-label binding, file task records, and MinIO object paths.
- Use MinIO or HTTP checks for file availability. Keep original file, transcoded file, and cover file separated in results.
- Distinguish video duration in seconds from relation segment duration in microseconds.
- Rerun/idempotency issues usually appear as duplicate videos, duplicate file records, or duplicate relation records.

## Suggested Verification Modules

1. `organization`
   - team, group, account, account-team/group, observer groups.
2. `basic_config`
   - category, tag group, tag item, category-tag binding, content state, default collection.
3. `media_master`
   - material and finished video master fields.
4. `file_result`
   - original, transcoded, cover file, target URL, MinIO object.
5. `material_relation`
   - finished video references material, segment start/duration, first segment, cover flag, track attributes.

## Required Report Focus

For this domain, conclusion should emphasize:

- Whether all expected source media exists in target.
- Whether target has extra or duplicate media.
- Whether field values are correct after ID mapping.
- Whether files are accessible.
- Whether finished-video-to-material references are complete and accurate.
