# TensorsLab Image API Reference

## Base URL

```
https://api.tensorslab.com
```

## Authentication

All requests require Bearer token authentication:

```
Authorization: Bearer <TENSORSLAB_API_KEY>
```

## Response Format

All responses follow this structure:

```json
{
  "code": 1000,
  "msg": "Success message",
  "data": { ... }
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 1000 | Success |
| 9000 | Insufficient Credits |
| 9999 | Error |

## Endpoints

### 1. Generate Image (SeeDream V4.5)

**Endpoint:** `POST /v1/images/seedreamv45`

**Recommended for:** General purpose, highest quality output

**Parameters (multipart/form-data):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Default: "seedreamv45" |
| `prompt` | string | Yes | Text description of desired image |
| `batchsize` | integer | No | Number of images (1-15), default: 1 |
| `resolution` | string | No | Aspect ratio (9:16, 16:9, 3:4, 4:3, 1:1, 2:3, 3:2), level (2K, 4K), or WxH |
| `sourceImage` | file[] | No | Source images for image-to-image |
| `imageUrl` | string | No | URL of source image for image-to-image |

**Resolution constraints:**
- Total pixels must be between 3,686,400 and 16,777,216
- Example: `3750x1250` is valid (4,687,500 pixels)
- Example: `1500x1500` is invalid (2,250,000 pixels - below minimum)

**Response:**

```json
{
  "code": 1000,
  "msg": "Task created successfully",
  "data": {
    "taskid": "abcd_1234567890abcdef"
  }
}
```

### 2. Generate Image (SeeDream V4)

**Endpoint:** `POST /v1/images/seedreamv4`

**Recommended for:** Faster generation with good quality

**Parameters (multipart/form-data):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Default: "seedreamv4" |
| `prompt` | string | Yes | Text description |
| `batchsize` | integer | No | 1-15, default: 1 |
| `resolution` | string | No | 9:16, 16:9, 3:4, 4:3, 1:1 |
| `sourceImage` | file[] | No | Source images |
| `imageUrl` | string | No | Source image URL |

### 3. Generate Image (SeeDream V5 Lite)

**Endpoint:** `POST /v1/images/seedreamv5`

**Recommended for:** New-generation text-to-image and image-to-image generation

**Parameters (multipart/form-data):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Default: `seedreamv5` |
| `prompt` | string | Yes | Text description |
| `batchsize` | integer | No | 1–15, default: 1 |
| `resolution` | string | No | Default: `2K` |
| `sourceImage` | file[] | No | Source images for image-to-image |
| `imageUrl` | string | No | URL of source image for image-to-image |

### 4. Generate Image (Z-Image)

**Endpoint:** `POST /v1/images/zimage`

**Recommended for:** Specific artistic styles

**Parameters (multipart/form-data):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Text description |
| `resolution` | string | No | Default: "1024*1024" (note asterisk) |
| `seed` | integer | No | Random seed for reproducibility |
| `prompt_extend` | string | No | "1" to enable prompt enhancement |

### 5. Query Task Status

**Endpoint:** `POST /v1/images/infobytaskid`

**Request Body (application/json):**

```json
{
  "taskid": "abcd_1234567890abcdef"
}
```

**Response:**

```json
{
  "code": 1000,
  "msg": "OK",
  "data": {
    "taskid": "abcd_1234567890abcdef",
    "category": "seedreamv45",
    "starttime": "2026-01-30 12:00:00",
    "url": ["https://example.com/image.jpg"],
    "image_status": 3,
    "width": 2048,
    "height": 2048,
    "prompt": "...",
    "negative": "...",
    "origseed": 12345
  }
}
```

### Image Status Codes

| Code | Status |
|------|--------|
| 1 | Queued |
| 2 | Processing |
| 3 | Completed (url array contains results) |
| 4 | Failed (check error_message field) |

### 6. Delete Task

**Endpoint:** `POST /v1/images/deleteimagestask`

**Request Body:**

```json
{
  "uid": "optional-user-id",
  "taskids": ["taskid1", "taskid2"]
}
```

## Error Handling

### Insufficient Credits (9000)

```json
{
  "code": 9000,
  "msg": "Insufficient credits"
}
```

**User message:** "亲，积分用完啦，请前往 https://tensorai.tensorslab.com/ 充值"

### Task Failed (image_status: 4)

```json
{
  "data": {
    "taskid": "...",
    "image_status": 4,
    "error_message": "Generation failed: specific reason"
  }
}
```

## Timeout

Request timeout: 180000ms (3 minutes)

For image generation, tasks run asynchronously. Poll the status endpoint until completion.
