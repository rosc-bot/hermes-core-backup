# Central Control Plane vs Edge Data Plane Architecture

## 1. Zero-Transit Bandwidth Decoupling
When orchestrating a multi-server Emby reverse proxy cluster:
- **Control Plane (Master UI)**: Runs on a centralized VPS (e.g. AWS EC2). Handles web administration, site configuration CRUD, node monitoring, and JSON payload synchronization to remote node agents over lightweight HTTP APIs (`<1KB` per sync).
- **Data Plane (Edge Nodes)**: Remote edge servers (TW / HK / NL) run optimized Nginx reverse proxy pipelines (`proxy_buffers 16 1m; proxy_max_temp_file_size 0;`).
- **Traffic Isolation**: Client video players (Infuse / VidHub / Hills) stream 4K HEVC / remux media (20GB+ files, 15-50Mbps bitrates) **directly** from the edge node IP.
- **Cost & Bandwidth Outcome**: The central master server incurs **zero transit bandwidth consumption** from media playback.

## 2. Cloud Firewall & Port Accessibility Constraints
- AWS EC2 Security Groups drop incoming connections on non-allowlisted ports by default.
- If running the control plane on AWS EC2, the designated management port (e.g. `18090` or `35087`) must be explicitly permitted in the Inbound Rules (`Custom TCP`, Port, Source `0.0.0.0/0`).
- Alternatively, hosting the master UI on a public edge node (e.g. Netherlands NAT on an open port) achieves identical zero-bandwidth transit impact while avoiding cloud security group configuration overhead.
