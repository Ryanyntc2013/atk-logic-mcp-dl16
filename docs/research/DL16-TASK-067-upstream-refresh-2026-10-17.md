# DL16-TASK-067 — 参考仓库更新与能力差异复核

调查日期：2026-10-17
证据等级：GITHUB_SOURCE_REVIEW / NO_LOCAL_HIL
范围：五个原有引用仓库 + 官方仓库两个未合并 PR
操作边界：仅查询公开 GitHub；不改原生后端、不发送 USB 命令。

## 结论

GitHub REST 查询了默认分支 HEAD、最近提交、compare(pin...HEAD)、branches、releases、pulls 和 issues。五个仓库的 compare.status 全为 identical；ahead_by=behind_by=0。**没有新默认分支提交需要引入，不升级 CPP pin。** 但官方仓库仍有未合并贡献，构成新的研究线索，而不是已发布行为。

| 代号 | 项目 | 固定 SHA = 默认 HEAD | 最后代码提交 | 差异 |
|---|---|---|---|---|
| VENDOR | https://github.com/alientek-openedv/atk-logic | 0dff562d24436def2bec3791684f1911997b9e35 | 2024-05-13 | IDENTICAL |
| VENDOR_SRD | https://github.com/alientek-openedv/atk_libsigrokdecode | 783fec96047f5859c2122ac79123a6929a35f75f | 2023-07-18 | IDENTICAL |
| CPP | https://github.com/gjjisadog/ATK-Logic-Mcp | 5fc47744c18c99f9ad0f554a965eb8cd1160c836 | 2026-09-14 | IDENTICAL |
| HUGEL | https://github.com/hugelzhang/atk-logic-mcp | 77320addfb34d3973d09a7af663de76023034587 | 2026-09-12 | IDENTICAL |
| LHX | https://github.com/LHX369963/dl16-cli | 8d7c209c1e3b13923620bb34cec915291a749612 | 2026-08-19 | IDENTICAL |

CPP 有已发布 GitHub release v1.1.0，发布时间 2026-09-14，无后续 release；其余四仓本轮没有 GitHub release。注意源码提交时间 != 软件发布版升级时间；官方 Windows GUI 最新闭源版本可能与 2024 年源码不同。

## 官方开源仓库中尚未合并的贡献

### PR #5 — Linux Qt5 build (OPEN, 2026-05-14)

https://github.com/alientek-openedv/atk-logic/pull/5

作者 mhpsy 报告 Arch Linux、Qt 5.15.18 构建、MCU/FPGA 版本交换和真机捕获。提案加入 Linux qmake 和依赖构建说明。关键风险：将 GUI 中 APP_VERSION_NUM 从 1066 改为 1199，以跨过其 FPGA 报告的最小版本 1108。**作者报告的版本门禁与修改版本号绕过门禁，不能证明固件协议兼容性**。不采用这种变更到本仓库；待有真实版本帧和行为证据再处理。

第三方 qBreakpad / libsigrokdecode 构建被报告存在 ABI、隐藏符号 SRD_PRIV 和头文件问题；作者的 symbol-visibility workaround 不宜视作生产方案。Linux GUI 构建和本项目 Windows 无 GUI C++ 后端没有直接升级关系。

### PR #4 — LCD8080 8-bit bus decoder (OPEN, 2025-12-31)

https://github.com/alientek-openedv/atk-logic/pull/4

新 Python PD 需 D0-D7 + /WR + A0/DC（10 路），可选 /CS（11 路），可设置沿后延迟。尚未合并和本地验收。**本项目 DEFAULT_MAX_CHANNELS=4 属于宽采集曾卡死的安全门禁**，不能为解码器而默认改为 10/11。可优先在离线历史波形与合成 10/11 路向量上开发独立解码器；现场宽采集另申请授权。

## 现有四个参考体系的改进价值

### CPP pinned native backend

无新提交，v1.1.0 仍是发布基线。其 README 声称跨进程设备独占锁及 DeviceBusy 行为，另有捕获证据门禁；而本项目 TASK-066 has_owned_session 仅检查进程内对象，不能证明跨进程互斥。后续通过双进程 mock 和单独授权的只读 DeviceBusy 现场用例确认，不自动关闭别的 GUI/Agent 会话。

参考：https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/README.md

### HUGEL Windows MCP

作者报告 208 个 sigrok PD、多层解码、总线探针和 .atkdl 由官方 GUI 打开测试。其文档记录所有 16 个通道的 channel.ini（即使空通道）及有效采样数对兼容性重要。本项目 atkdl_export.py 明确只是 offline-reader subset / GUI UNVERIFIED。建议先做构造 ZIP/INI 离线对照，再单独进行 GUI 打开验收，勿提前标记兼容。

HUGEL 报告 RLE 真实压缩成功，但这不是本设备当前 Windows Native RLE 验证；本项目 RLE 继续 fail-closed，不移植其它作者的设备恢复或默认开压缩。sigrok 宿主与堆叠 PD 可以研究为可选离线功能，保持 GPL/依赖出处与权限界限。

参考：https://github.com/hugelzhang/atk-logic-mcp/blob/77320addfb34d3973d09a7af663de76023034587/atk-logic/TEST-REPORT.md

### LHX Linux PyUSB

默认 HEAD 2026-08-19 未变。LHX 为初始化失败后才执行特定设备恢复，支持持久会话、PWM/Buffer/RLE/Stream 和显式物理回环映射；其跨操作系统 USB clear_halt/reset 不可直接移植到 WinUSB。其 Stream 截断规则是作者设备/协议版本观察，本项目仍存在 8/16 字节不同尾部，不可因此提高数据完整性标记。此 GitHub 快照未发现显式 LICENSE；不得复制其实现代码。

参考：https://github.com/LHX369963/dl16-cli/tree/8d7c209c1e3b13923620bb34cec915291a749612

### 官方协议解码 fork

VENDOR_SRD 仍未出现新默认分支提交。Linux PR #5 提及其隐符号链接问题；这属于独立 GUI 构建任务，不是运行时协议变化。

## 决策和下一任务（按优先级）

| 优先级 | 需要完善的事项 | 证据要求 | 现在是否改硬件协议 |
|---|---|---|---|
| P0 | TASK-066 实物 PWM 断输出 / 失败清理，以及多 MCP client/GUI 设备所有权 | 模拟故障 + 独立示波器 + 有界人工授权 | 否 |
| P1 | .atkdl 官方 GUI 兼容性格式矩阵 | 离线 ZIP/INI golden + GUI 人工打开 | 否 |
| P1 | 独占设备的第二进程拒绝和回收语义 | 进程级 mock + 单独授权 HIL | 否 |
| P2 | LCD8080 可选离线解码器 | 10/11 路向量，另论宽通道安全 | 否 |
| P2 | sigrok 分层协议解码宿主 | 离线 golden、许可证审查、受限依赖 | 否 |
| P3 | 官方 Linux Qt GUI 构建兼容性 | 构建环境/ABI/许可；拒绝虚改 APP_VERSION_NUM | 否 |
| BLOCKED | RLE / 未知 Stream trailer 裁剪 | 字节级多模式实物证据 | 保持 UNKNOWN |

工程决定：冻结当前 CPP pin 和已审核协议向量；TASK-066 独立 PR 继续验收，TASK-067 只更新参考资料，不混入运行时代码。

## 下次核对机制

依照显式 pin 查询 5 个默认分支 commit SHA / date，用 GitHub compare API 判定 ahead_by；分别查询 releases、open PR/issue，防止仅凭仓库 updated_at 当作提交。遇到网络/API 错误标 UNKNOWN，不报告无更新。发现新 commit 后先 diff/版权审查，再构造离线向量，最后才单独申请真机实验和 repin 决策。

证据分层：GitHub commit/PR/release 是 REMOTE_SOURCE；其他作者的设备报告是 REPORTED_HIL；此次未连接真实 DL16，因此所有硬件问题仍为 HIL_NOT_RUN。
