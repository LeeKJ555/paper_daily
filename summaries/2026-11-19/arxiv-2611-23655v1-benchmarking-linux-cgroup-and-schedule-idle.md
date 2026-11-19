## 论文针对什么问题

论文关注 Linux cgroups 与 `SCHED_IDLE` 调度策略在 serverless 场景下的性能隔离能力。很多 serverless 平台/运行时（如 Mitosis、gVisor、Harvest VM、FAASM）依赖基于 cgroups/namespaces 的 Linux 容器做资源隔离，但这一内核原语是否真正适配 serverless 需求仍不清楚。具体问题包括：

- Linux CFS 调度器如何处理 cgroups 与 `SCHED_IDLE`？
- 高尾延迟的核心来源是什么？
- 是否有必要设计新的隔离原语？

论文选择先通过基准测试刻画当前 cgroups 与 sched idle 策略在“延迟关键（LC）服务器 + 后台（BE）密集任务”共存场景下的行为，尤其关注这两个原语对 LC 服务器性能尾延迟的影响，以及 LC 尾延迟与 BE 吞吐量之间的权衡。

## 提出了什么解决方案

论文没有提出新的内核原语或调度算法，而是提出了一个基准测试套件 **cgroup-benchmark**，用于系统性地模拟和比较不同内核隔离/调度配置下，LC 服务器在 BE 任务干扰下的表现。

该套件通过模拟 LC TCP 服务器与内存密集型 BE 矩阵乘法任务共存的环境，对比以下配置：

- baseline：不使用 cgroups，BE 使用默认调度策略；
- cgroup-weight：使用 cgroup `cpu.weight` 按比例分配 CPU 时间；
- cgroup-max：使用 cgroup `cpu.max` 限制 BE 后台任务的最大 CPU 带宽；
- cgroup-sched idle-weight：结合 cgroup 与 `SCHED_IDLE` 策略；
- cgroup-sched idle-max：结合 cgroup 带宽限制与 `SCHED_IDLE`；
- sched idle：仅对 BE 任务使用 `SCHED_IDLE`，不使用 cgroups。

目标是识别哪些原语和配置能有效降低 LC 尾延迟，同时观察对 BE 吞吐量的影响，并为进一步研究提供实验基础。

## 具体是怎么做的

### 基准测试组件

- **BE 后台任务**：`matmul.py <nrows> <ncols>`，使用 numpy 实现多线程矩阵乘法。
- **LC 服务器**：多线程 TCP 服务器，C++ 实现，每个客户端连接创建一个线程。`mm=TRUE` 时，服务器收到请求后执行一次 `nrows×ncols` 矩阵乘法再响应；`mm=FALSE` 时立即响应。
- **客户端**：持续 ping 服务器并记录观测到的 RTT。

### 实验场景

论文设置了三种服务器负载场景：

1. **轻负载（Light Server Load）**：服务器不执行矩阵乘法，收到请求立即响应。BE 任务为 500×500 矩阵乘法。
2. **重负载（Heavy Server Load）**：服务器每次请求执行 500×500 矩阵乘法。
3. **合理负载（Reasonable Server Load）**：服务器每次请求执行 100×100 矩阵乘法。

### 实验配置

对每种场景测试六种配置（baseline、cgroup-weight、cgroup-max、cgroup-sched idle-weight、cgroup-sched idle-max、sched idle）。BE 任务在测试开始 30 秒后启动，16 个客户端并发访问。

cgroup 权重设置为 `server:background = 2048:1024`；`cpu.max` 设置中后台任务最大为 50% CPU 带宽。

### 实验环境

- 平台：Cloudlab 2-node LAN
- 每节点：16 核
- Linux 内核：5.15.0-86-generic（使用 CFS 调度器）
- 客户端数量：16（与核数相等）
- CPU 频率：所有核心固定为最大值 2000 mHz

### 评估指标

主要评估指标为：

- LC 服务器响应延迟的 P50、P99、P99.99；
- BE 矩阵乘法的延迟或吞吐量变化；
- 启动 BE 任务前后尾延迟的相对变化。

## 取得了什么效果

### 合理服务器负载（100×100 矩阵乘法）

- **baseline**：启动 BE 任务后，P50 下降 18%，P99 增加 30%，P99.99 增加 50%。
- **cgroup（cpu.weight）**：P50 下降 4%，P99 增加 15%，P99.99 增加 30%。总体比 baseline 更稳定，启动 BE 任务对尾延迟的影响更小；99.9% 尾延迟相比 baseline 降低约 12%。
- **cgroup + sched idle**：P50 下降 9%，P99 增加 12%，P99.99 增加 65%。P99 相比无 sched idle 时改善约 5%，且延迟波动范围更小。
- **仅 sched idle**：P50 下降 3%，P99 增加 0.1%，P99.99 增加 0.4%。LC 尾延迟最稳定，但 BE 矩阵乘法吞吐量下降 7.5 倍。

### 轻服务器负载

- baseline 和 cgroup 配置下，启动 BE 任务后反而出现 P50 下降等现象，论文认为可能是 BE 任务预热并稳定了 CPU 频率。
- 添加 sched idle 后，极端尾延迟尖峰被完全消除。例如 cgroup+sched idle 下，启动 BE 后 P99.99 反而从约 1.0 ms 降到 0.65 ms，而 baseline 下从 0.98 ms 升到 1.23 ms。

### 重服务器负载

- 总体 RTT 粒度较大，尾延迟尖峰更难检测，但 cgroup 与 sched idle 仍有轻微改善。
- 无 sched idle 时，启动 BE 任务后 P50 增加 57%；使用 sched idle 时，P50 增加幅度降至 32%。

### 结论

- `SCHED_IDLE` 策略对减少一次性尾延迟尖峰至关重要。
- 论文推测其机制是：sched idle 使服务器进程对一组 CPU 核心具有更强的亲和性，减少任务跨核迁移，从而减少数据包到达不同核心导致的额外 CPU 开销。
- 但论文也指出，还需要进一步工作来完整解释尾延迟尖峰的原因。

## 旁观者视角的问题与不足

- **工作负载单一**：BE 任务只有矩阵乘法（CPU/内存密集型），未覆盖 I/O 密集型、网络密集型或多种资源混合争用场景；LC 服务器也只是简单 TCP echo 或矩阵乘法，与真实 serverless 平台（如 gVisor、Firecracker、FAASM）中的请求处理路径差异较大。
- **统计严谨性不足**：原文未提供实验重复次数、是否多次运行取平均、是否存在误差棒/置信区间等信息，尾延迟数字容易受单次运行噪声影响。
- **配置描述存在不一致**：例如 `cgroup-sched idle-max` 与 `sched idle` 的文本描述和配置名称不完全对应，可能导致复现困难。
- **bandwidth 限制结果报告不充分**：论文主要报告了 `cpu.weight` 的结果，声称也测试了 `cpu.max`，但未给出 `cpu.max` 的完整数据，因此无法评估硬带宽限制的实际效果。
- **未明确 cgroups 版本**：背景部分引用了 cgroups v2 文档，但实验环境未明确说明使用的是 cgroups v1 还是 v2，而两者 CPU 控制器行为存在差异。
- **尾延迟根因缺乏实证**：论文提出了“CPU 亲和性/任务迁移减少”的理论，但没有给出内核 trace、性能计数器或调度器事件等证据，只能说明相关性而非因果性。
- **客户端数量固定**：16 个客户端与 16 核完全匹配，可能避免了 CPU 过度订阅的最坏情况，掩盖了更真实场景下的争用问题。
- **电源管理影响未完全消除**：虽然 CPU 频率被固定为最大 2000 mHz，但轻负载下启动 BE 任务仍导致 LC 性能提升，说明存在频率之外的热/功耗状态影响，实验未进一步控制。

## 值得继续追踪的点

- 使用内核追踪工具（如 trace-cmd、KernelShark、flame graph）定位尾延迟尖峰的具体来源。
- 通过 CPU pinning 实验区分跨核调度与单核内 CPU 时间分配对尾延迟的影响。
- 动态调整客户端数量，而非固定 16 个，以观察不同程度 CPU 争用下各原语的表现。
- 更全面地评估 `cpu.max` 硬带宽限制与 `cpu.weight`、`SCHED_IDLE`、nice 优先级之间的交互。
- 在更接近真实 serverless 工作负载（短生命周期、高并发、冷启动频繁）的环境中验证这些原语。
- 与已有延迟感知调度工作（如 “Towards Latency-Aware Linux Scheduling for Serverless Workloads”）进行对比，进一步判断现有原语是否足够，还是需要新原语设计。

## 元数据与链接

- **标题**：Benchmarking Linux CGroup and Schedule Idle
- **作者**：Anna Arpaci-Dusseau
- **来源**：arXiv
- **Venue**：arXiv cs.OS
- **DOI**：N/A
- **原文链接**：[http://arxiv.org/abs/2611.23655v1](http://arxiv.org/abs/2611.23655v1)
- **PDF 链接**：[https://arxiv.org/pdf/2611.23655v1](https://arxiv.org/pdf/2611.23655v1)
- **匹配主题**：os-kernel, systems
- **相关性分数**：8

> 注：本文为 arXiv 预印本，实验评估与结论尚未经过正式同行评议。
