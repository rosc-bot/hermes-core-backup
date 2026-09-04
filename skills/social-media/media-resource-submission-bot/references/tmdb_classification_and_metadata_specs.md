# TMDB Classification Taxonomy & Metadata Scraping Specifications

## 1. Directory Tree Taxonomy (Emby / Jellyfin Standard)

Under the master cloud directory (`📁 影视转存总目录`):

```text
📁 影视转存总目录
├── 📁 电视剧
│   ├── 📁 儿童 (Children / Kids Animations & Shows)
│   ├── 📁 国产剧 (Domestic Chinese Mainland / HK / TW TV Shows)
│   ├── 📁 国漫 (Chinese Animation / Donghua)
│   ├── 📁 纪录片 (Documentaries)
│   ├── 📁 欧美动漫 (Western Animation: US / EU / UK)
│   ├── 📁 欧美剧 (Western TV Shows: US / UK / Canada / Europe)
│   ├── 📁 其他剧 (Other foreign series: Thai, Indian, etc.)
│   ├── 📁 日番 (Japanese Anime)
│   ├── 📁 日韩剧 (Japanese & Korean Live-Action Dramas)
│   └── 📁 综艺 (Variety & Reality Shows)
└── 📁 电影
    ├── 📁 动画电影 (Animated Movies)
    ├── 📁 华语电影 (Chinese-Language Movies: CN, HK, TW)
    ├── 📁 欧美电影 (Western Movies: US, UK, FR, DE, etc.)
    ├── 📁 日韩电影 (Japanese & Korean Live-Action Movies)
    ├── 📁 外语电影 (Other Foreign Language Movies)
    └── 📁 其他电影 (Fallback category)
```

## 2. Media Classification Rules (`MediaClassifier`)

### 2.1 TV / Series Classification
- **国漫**: `is_anime` AND `CN/TW/HK` country OR Chinese language (`zh`, `cmn`).
- **日番**: `is_anime` AND `JP` country OR `ja` language.
- **欧美动漫**: `is_anime` AND `US/GB/FR/DE/CA/AU` country OR `en/fr/de` language.
- **儿童**: Genres include `Kids` (10762) or keywords indicate child/preschool content.
- **纪录片**: Genres include `Documentary` (99).
- **综艺**: Genres include `Reality` (10764) or `Talk` (10767).
- **国产剧**: Non-anime series with origin country in `CN`, `HK`, `TW` or `zh` language.
- **日韩剧**: Non-anime series with origin country in `JP`, `KR` or `ja`, `ko` language.
- **欧美剧**: Non-anime series with origin country in Western territories (`US`, `GB`, `CA`, etc.).
- **其他剧**: Fallback for series from other origins (e.g. `TH`, `IN`).

### 2.2 Movie Classification
- **动画电影**: Genres include `Animation` (16) or media type is `ANIME`.
- **华语电影**: Origin country in `CN`, `HK`, `TW` or `zh` language.
- **欧美电影**: Origin country in Western regions (`US`, `GB`, `FR`, etc.) or `en`, `fr`, etc.
- **日韩电影**: Origin country in `JP`, `KR` or `ja`, `ko` language.
- **外语电影**: Other foreign productions (e.g. `IN`, `TH`, `RU`).
- **其他电影**: Fallback for movies.

## 3. Metadata Scraper & Assets Specification (`scripts/download_metadata.py`)

### 3.1 NFO File Architecture
- **TV Series**: Generates `tvshow.nfo` in the root of the media subfolder. Contains: `<title>`, `<originaltitle>`, `<rating>`, `<year>`, `<plot>`, `<id>`, `<tmdbid>`, `<genre>`, `<studio>`, `<director>`, `<actor>` nodes with profile paths.
- **Movie**: Generates `movie.nfo` in the root of the media subfolder.

### 3.2 Visual Assets
- **Poster**: `poster.jpg` downloaded from TMDB `original` image endpoint.
- **Fanart / Backdrop**: `fanart.jpg` downloaded from TMDB `original` backdrop endpoint.
- **Actor Avatars**: Saved under hidden directory `.actors/<Actor_Name>.jpg` using TMDB `w185` profile image endpoint.

### 3.3 Strict Request Rate Limiting
- TMDB API rate limit boundary: Strictly bounded $\le$ 30 requests per second (`max_requests=30, window_seconds=1.0`).
- Implemented via sliding-window async token/timestamp queue.

### 3.4 Concurrency & Review Lock Discipline (`TaskReviewLock`)
- Core business (user submission review, admin approvals) has absolute priority over background metadata downloads.
- File-based / async context lock (`/tmp/media_bot_task_review.lock`):
  - When review operations start, lock is acquired.
  - Metadata scraping checks `TaskReviewLock.is_review_active()`. If active, scraping gracefully waits or defers, guaranteeing 0 resource contention or database contention with admin operations.
