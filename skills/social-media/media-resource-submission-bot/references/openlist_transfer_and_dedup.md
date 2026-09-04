# Channel-Bound Auto-Transfer, Master Folder & Storage Architecture

## 1. Architectural Choice: Option 1 vs Option 2

| Dimension | Option 1: Native Direct Transfer (Active Baseline) | Option 2: OpenList Mount (Streaming Mode) |
| :--- | :--- | :--- |
| **Primary Goal** | Automated cloud transfer, master folder grouping, dedup, official share links | Emby/Jellyfin direct playback via WebDAV / local mount |
| **Daemon Required** | ❌ None (0 daemons, pure Python in bot process) | 🟢 `openlist.service` (OpenList / AList v4) |
| **Port Required** | ❌ None (0 network ports) | 🟢 Port `12666` or `39637` |
| **Server Bandwidth** | ❌ Zero (transfer happens server-to-server in cloud) | ⚠️ Proxy streaming consumes egress when active |
| **Storage Pattern** | Direct API (`GuangyaTransferAdapter`, `MobileTransferAdapter`) | OpenList REST API (`/api/fs/*`) + WebDAV |
| **When to Use** | Default operational baseline when only managing channel resources | Only when user explicitly requests Emby cloud mount streaming |

---

## 2. Option 1 Channel-Bound Transfer Pipeline Architecture

```text
投稿通过审核 (ACCEPTED)
   ↓
🎯 1. 频道与网盘映射识别 (cloud_cfg.channel_id)
   • 光鸭资源 ➡️ 发布到光鸭专属频道 (-1004387965244) ➡️ 路由至 GuangyaTransferAdapter (用户光鸭网盘)
   • 移动云盘 ➡️ 发布到移动专属频道 (-1004410413711) ➡️ 路由至 MobileTransferAdapter (用户移动云盘)
   • 夸克/阿里/115 ➡️ 依据 /clouds 绑定的对应适配器与专属频道路由
   ↓
📁 2. 网盘总文件夹自动创建与聚合
   • 检查网盘根目录是否存在指定的总文件夹 (默认: `影视转存总目录`，可通过 `/setcloud` 自定义)
   • 若不存在，自动在用户网盘根目录创建 `影视转存总目录`
   • 在总文件夹内部，自动创建/定位标准子目录：
     `影视转存总目录/{剧名(年份)第X季 4K {tmdbid-ID}}/`
   ↓
🔍 3. 双层智能查重与增量转存 (Deduplication)
   • 扫描目标目录已有文件清单；
   • 对比集数标识 (E01, E02 等)；
   • 自动跳过重复已有集数，仅转存缺失新增集数；
   ↓
📢 4. 频道推送成功消息 (无需生成新分享链接)
   • 默认不生成新分享链接 (`auto_share=False`)，保护网盘私密性；
   • 将去重状态、转存结果与原投稿分享链接组合为规范卡片，直接推送到绑定的 Telegram 频道。
```

---

## 3. Admin Management Commands

- `/clouds`: Inspect all configured cloud drives, auto-transfer modes, target master directories (`📁 影视转存总目录`), and token status with one-tap toggle buttons.
- `/setcloud <name> <token> [folder_id/name]`: Configure auth tokens / cookies and custom master folder names.
  - *Example*: `/setcloud guangya eyJhbGciOi... 影视转存总目录`
