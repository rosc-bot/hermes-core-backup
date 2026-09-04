# Windows Update Group Policy & Intel Wi-Fi BSOD Diagnostics

## 1. Windows Update Policy Lock (`AUOptions` / 组策略管理员接管)

### 现象
在 Windows 设置 -> Windows 更新中提示「某些设置由你的组织来管理」，并在「设备设置的策略」列表中显示：
- **设置自动更新选项**（源: 管理员，类型: 组策略）
- **自动下载更新并在准备好安装时通知**（源: 管理员，类型: 组策略）

### 根因
组策略或第三方优化软件写入了注册表键值：
`HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU` 中的 `AUOptions` (值通常为 3，代表自动下载但在安装前通知)。该界面为只读状态列表，无法直接在设置界面开关。

### 解决与恢复默认自动更新
1. **组策略方式（Win Pro / Enterprise）**：
   - 运行 `gpedit.msc` -> 计算机配置 -> 管理模板 -> Windows 组件 -> Windows 更新。
   - 找到「配置自动更新」，双击设为「未配置」（恢复默认）或「已启用 - 4 自动下载并计划安装」。
   - 执行 `gpupdate /force`。
2. **命令行/注册表快速解除（全版本通用）**：
   - 管理员身份打开终端，删除锁定项：
     ```cmd
     reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v AUOptions /f
     ```
   - 重启 Windows 更新服务：
     - **PowerShell 语法**：`Restart-Service wuauserv`（注意：PowerShell 中严禁使用单个 `&` 拼接命令，会报 `ParserError: AmpersandNotAllowed`；可改用分号 `;` 或原生 Cmdlet）。
     - **CMD 语法**：`net stop wuauserv & net start wuauserv`。
   - 返回设置页点击「检查更新」，策略提示自动消除。

---

## 2. Intel Wi-Fi 网卡驱动导致 Windows 蓝屏/黑屏死机 (`Netwbw02.sys`)

### 现象
系统突发黑屏/蓝屏死机，提示：
- **Stop Code (终止代码)**：`KMODE_EXCEPTION_NOT_HANDLED (0x1E)`
- **What failed (失败模块)**：`Netwbw02.sys`

### 根因
`Netwbw02.sys` 是 Intel Wireless Wi-Fi Link 无线网卡官方底层内核驱动程序。当驱动版本与 Windows 新内核存在内存管理冲突、休眠唤醒竞态或驱动文件损坏时，会触发内核未捕获异常导致停机保护。

### 解决步骤
1. **更新/重装 Intel 无线网卡官方驱动**：
   - `Win + X` 打开「设备管理器」->「网络适配器」-> 找到 `Intel(R) Wi-Fi` / `Intel(R) Wireless-AC` 设备。
   - 前往 Intel 官网下载最新版「Intel PROSet/Wireless Software & Drivers」驱动包进行覆盖安装。
2. **临时防复发（关闭快速启动）**：
   - `Win + R` 运行 `powercfg.cpl` 打开电源选项 ->「选择电源按钮的功能」-> 取消勾选「启用快速启动 (推荐)」。
   - 可避免系统从休眠/伪关机状态恢复时因网卡内核状态未完全初始化导致的内存冲突。
