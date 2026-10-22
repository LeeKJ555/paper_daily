## 论文针对什么问题

HPC 设施多年积累了大量作业调度器记录，但这些运营数据大多未被充分利用，原因在于缺少能把记录转化为可操作见解的易用工具。运营团队通常需要回答两类问题：

- **离线回顾性问题**：例如在不同优先级策略或 backfilling 策略下，平均等待时间会如何变化；某策略是否以利用率为代价换取公平性。这类问题需要完整 trace 重放。
- **在线实时问题**：在没有未来工作负载知识的情况下，针对当前排队作业评估替代调度策略，为实时决策提供指导。

论文认为，现有工具的主要缺口不只是缺少模拟方法，而是缺少将模拟方法与日常设施运营决策连接起来的、操作上可用的分析工具。现有模拟器多面向离线 trace replay 或源码级扩展，在线决策支持与面向 facility staff 的交互式工作流非常有限。

## 提出了什么解决方案

论文提出 **CQTwin**，一个开源、面向 HPC 调度器运营分析的数字孪生工具包。它基于 Python 的 CQSim 离散事件模拟器构建，保留其调度语义，并增加：

- 经过保真度验证的高性能 C++ 离散事件引擎；
- 在线事件流接口；
- 交互式浏览器仪表盘；
- Snapshot Lab。

CQTwin 提供两种互补模式：**离线 trace replay** 和 **在线 event-driven simulation**。目标是让设施工作人员、运营者和研究人员能够进行工作负载特征分析、调度策略比较和 what-if 场景探索，而无需修改生产系统或将运营数据转移离线。

## 具体是怎么做的

CQTwin 构建在 CQSim 之上，核心是一个经过保真度验证的高性能 C++ 离散事件引擎，并提供 Python 侧接口。主要工作流如下：

- **离线数字孪生**：读取完整生产 trace，按作业记录中的到达时间提交作业，由选定调度策略和 backfilling 策略决定作业开始时间，从而在相同 workload 下比较不同策略的总体结果。
- **在线数字孪生**：以事件流方式消费作业事件，不依赖未来 workload 知识；在当前排队作业上投影替代策略的处理结果，为实时决策提供指导。默认投影不改变已提交调度；也可以通过 Gym-style 外部接口，在每决策周期由外部控制器选择 dispatch policy，实现端到端外部策略控制。
- **浏览器仪表盘**：覆盖分析前、中、后三个阶段。分析前直接从 SWF 做 workload characterization，包含六个面板：runtime 和 requested-processor 分布、按 runtime class 的 wait time、requested vs actual runtime、job arrival rate vs average wait、以及 makespan 内的 requested load。分析中支持实验配置与监控；分析后支持多维对比模拟结果。
- **Snapshot Lab**：摘要提到作为工具的一部分，但正文摘录/摘要未提供其具体机制与功能细节。
- **数据与验证**：使用 Argonne Leadership Computing Facility 2016–2023 生产 traces，具体包含 Mira-2016、Theta-2021、Polaris-2023。

## 取得了什么效果

- **保真度**：C++ 引擎逐作业复现 Python CQSim 的调度决策；正文摘录提到在 5 种调度策略、超过 50,000 个作业上验证了一致性，并且在线 stream-fed 运行在完整 Polaris-2023 trace（147,513 个作业）上完全重现 trace-driven replay，建立从事件流到参考实现的端到端等价链。
- **性能**：C++ 引擎回放一年生产 trace 仅需 2.3 秒，相比原 Python CQSim 最高加速 24×。
- **在线开销**：每决策周期的在线投影增加约 0.66 ms 开销，同时不改变 committed schedule。
- **外部策略控制**：通过 Gym-style 接口，一个 greedy 控制器在一年长运行中切换 committed policy 3,084 次，演示了端到端外部策略控制。
- **工程产物**：代码开源，ALCF 生产 traces 公开可用。

## 旁观者视角的问题与不足

- **资源模型受限**：论文明确说明当前 CQTwin 只建模 whole-node allocation，不支持 GPU、内存、异构节点类型或其他多资源约束；也不包括能源、功率、冷却、温度等设施遥测。这类更完整的数字孪生是 ExaDigiT 等系统的目标，不是 CQTwin 当前范围。
- **在线模式的定位偏“建议”而非“闭环”**：在线投影默认不改变 committed schedule，实际策略切换需要外部程序通过 Gym-style 接口完成。论文未展示在生产调度器中闭环接入后的稳定性、错误恢复或与真实调度器的交互代价。
- **验证范围集中于 ALCF**：实验基于 Mira-2016、Theta-2021、Polaris-2023 三个 ALCF traces，对其它站点、其它调度器配置或不同 backfill 变体的泛化性尚未在现有材料中体现。
- **缺少面向可用性的评估**：现有验证主要关注引擎保真度、速度和接口可行性；对 dashboard 是否真正降低 facility staff 的分析门槛、Snapshot Lab 的用途、以及用户工作流有效性，原文摘录/摘要未提供足够信息。
- **与既有工具缺乏定量对比**：相关工作中讨论了 Alea、Slurm Simulator 等，但未看到 CQTwin 与这些模拟器在功能、性能或可用性上的定量比较。

## 值得继续追踪的点

- 扩展多资源和异构节点调度模型：GPU、内存、NUMA/拓扑、异构 node type 等，直接影响现代 HPC 调度保真度。
- 将 CQTwin 与 ExaDigiT 等设施级数字孪生结合，纳入能源、散热、功耗等遥测，形成更完整的数据中心运营分析链路。
- 基于 Gym-style 外部接口研究在线学习/自适应调度策略，尤其是投影辅助下的在线决策效果、稳定性与安全性。
- 跨站点、多调度器 traces 验证，以及事件流格式/接口标准化，降低其他设施接入成本。
- Snapshot Lab 的具体机制、用途和用户反馈；运营人员使用 dashboard 的工作流效率和 adoption 评估。
- 在线投影的延迟、吞吐和与真实调度器事件流集成的工程问题。

## 元数据与链接

- 标题：CQTwin: A Digital-Twin Toolkit for Operational Analytics of HPC Schedulers
- 作者：Kanglin Xu, Yash Kurkure, Yihe Zhang, Michael E. Papka, Zhiling Lan
- 来源：arXiv
- Venue：arXiv cs.DC, cs.PF
- DOI：N/A
- 原文链接：http://arxiv.org/abs/2610.26609v1
- PDF 链接：https://arxiv.org/pdf/2610.26609v1
- 匹配主题：systems
- 相关性分数：9
- 代码：https://github.com/SPEAR-UIC/CQTwin
- 数据：ALCF 生产 traces（Mira-2016, Theta-2021, Polaris-2023）公开可用
