## 论文针对什么问题

GPU 在 AI 负载中需求旺盛，但实际利用率常常偏低（例如 Meta 广告推理服务一周内利用率仅 20%–40%，Microsoft 也报告不超过 50%），这催生了在单块 GPU 上混部（colocate）多个工作负载以提高资源利用率的需求。然而，并发执行会争用共享 GPU 资源，导致延迟关键型（latency-critical）工作负载的性能下降，干扰问题成为 GPU 共享的核心障碍。

现有 GPU 调度器抑制干扰的方法主要有两类：

1. **启发式调度**：依赖 SM 占用率、内存带宽、总体计算/访存使用量等粗粒度指标。这些指标只覆盖少数干扰来源，容易导致次优调度决策。
2. **干扰预测器**：不少方法依赖 GPU 模拟器中的性能指标，在真实硬件上不可用或难以获取；即使面向真实硬件的方法也常使用粗粒度性能计数器，难以刻画 kernel 间复杂的干扰交互。

论文指出，GPU 干扰来源复杂，至少涉及线程块放置、内存层级争用、SM 内部资源争用等多个机制。现有启发式或粗粒度预测器无法充分捕捉这些机制，导致预测误差大，低估或高估 colocation 带来的 slowdown。因此，需要一种准确、基于真实硬件、kernel 粒度的干扰预测方法，既能跨应用泛化，又能捕捉多种 GPU 资源争用来源。

## 提出了什么解决方案

论文提出 **Mosaic** 和 **MosaicSched**：

- **Mosaic** 是一个 kernel 级 GPU 干扰预测器，输入两个 GPU kernel 及其隔离执行 profile（通过 Nsight Systems 收集的选定指标），显式建模线程块放置、内存层级争用、SM 内部资源争用等干扰机制。它结合分析模型与轻量级学习模型，在真实 GPU 上实现更准确的 colocation slowdown 预测。
- **MosaicSched** 是基于 Mosaic 的在线调度器，执行 kernel 准入控制，并在两种 colocation 模式间选择：
  - 全 GPU colocation：多个 kernel 共享整块 GPU；
  - SM 分区：利用 CUDA Green Contexts 将每个工作负载限制到专用 SM 子集，降低干扰但限制可用资源。

MosaicSched 的目标是在满足高优先级工作负载延迟 SLO 的前提下，最大化 best-effort 工作负载吞吐量。

## 具体是怎么做的

根据摘要和开放 PDF 正文摘录，方案可以归纳为：

- **预测器设计**：Mosaic 显式建模 GPU 干扰的多个机制：thread-block placement、memory hierarchy contention、intra-SM resource contention。它使用分析模型和轻量学习模型相结合，输入为两个 kernel 及其隔离执行 profile，这些 profile 使用 Nsight Systems 收集的选定指标构建。
- **调度器设计**：MosaicSched 进行在线 kernel 准入控制，并选择全 GPU colocation 或 SM partitioning。SM partitioning 通过 CUDA Green Contexts 实现，每个工作负载被限制到专用 SM 子集。调度决策的目标是最大化 best-effort 吞吐量，同时满足延迟 SLO。
- **关键观察**（来自正文摘录后的讨论）：
  - 全 GPU colocation 为 best-effort kernel 提供更多资源，但可能带来更强的干扰，从而减少 best-effort 准入机会。
  - SM partitioning 减少干扰，但限制 best-effort 可获得的最大吞吐量，且最优 partition 划分强烈依赖于工作负载的计算和内存特性。
  - 没有一种 colocation 模式对所有工作负载对都普遍最优。
  - 最大化 GPU 利用率并不一定最小化部署成本：有时为了满足高优先级延迟目标，需要大幅节流 best-effort 负载，反而使共享 GPU 失去成本优势。

原文摘录在“具体是怎么做的”上仍有些部分被截断（例如预测器训练数据、学习模型结构、分析模型公式、调度器决策频率等），因此完整机制细节无法从所提供材料中完全确认。

## 取得了什么效果

- **预测精度**：在四个 GPU 架构上，Mosaic 相比先前预测器将预测误差降低最多一个数量级（up to an order of magnitude）。
- **延迟保障**：在所有工作负载和 SLO 目标下，MosaicSched 保持 p99 延迟低于或非常接近目标 SLO。
- **经验发现**：
  - 全 GPU colocation 与 SM partitioning 之间没有普适最优选择，取决于双方工作负载的资源特性。
  - 单纯提高 GPU 利用率不一定降低部署成本；过度节流 best-effort 负载可能抵消共享收益。

注意：摘要和提供正文未给出具体实验平台、数据集、SLO 数值、baseline 名称（除 Orion 和 Green-Context-based scheduling 在图 1 中出现）以及误差绝对数值。上述效果基于论文摘要的自述结果。

## 旁观者视角的问题与不足

- **评估覆盖与指标透明度不足**：摘要只说“在四个 GPU 架构上”降低预测误差，但未列出具体架构型号、驱动/CUDA 版本、工作负载类型和数量。p99 延迟的测量范围也未澄清：是单个 kernel 执行 p99 还是端到端请求 p99？如果只测量 kernel 级延迟，可能忽略 CPU 排队、数据拷贝、batch 组装等端到端干扰来源，不一定能完全代表服务级 SLO。
- **预测器对 profile 和硬件暴露度的依赖**：Mosaic 依赖 Nsight Systems 采集的隔离执行 profile。这些 profile 可能需要在目标 GPU 上预先采集，实际部署时对未见过的 kernel 或动态图、可变输入形状场景是否仍能保持准确，原文摘录未提供足够信息。不同 GPU 架构/驱动版本下可用 performance counter 集合可能变化，如何保证跨架构泛化需要进一步说明。
- **在线调度开销和更新机制未明确**：MosaicSched 的准入控制需要在线预测。预测器推理开销、调度决策频率、是否需要在线更新学习模型、以及 kernel 执行时间很短时调度器是否可能成为瓶颈，摘要和提供的正文均未给出细节。
- **与现有软件/硬件隔离机制的关系不清晰**：论文提到 SM partitioning 基于 CUDA Green Contexts，但未说明与 NVIDIA MIG、MPS、CUDA streams 等方式的差异或局限性。Green Contexts 是否为所有 GPU 架构支持、是否有额外限制，摘录未提供足够信息。
- **“显式建模干扰机制”的可解释性尚待验证**：虽然论文声称显式建模三种机制，但如何从真实 GPU 上采集的有限 counter 中准确分离和量化这些机制，摘要中未给出具体方法。这可能依赖较强的简化和经验假设，实际预测误差仍可能在某些工作负载上显著。
- **潜在的可复现性问题**：公开 PDF 摘录中包含多处文本截断、重复（如 MosaicSched 描述被重复），且 arXiv 链接为 2610.07504，尚无 DOI，这增加了第三方验证和阅读全文的困难，也可能影响对论文完整性的判断。

## 值得继续追踪的点

- 是否开源 Mosaic 与 MosaicSched 的代码及采集 profile 的流程，以及在哪些具体 GPU 上做过验证。
- 与 NVIDIA MIG、MPS、CUDA Green Contexts 的对比，特别是在安全隔离、抢占、设备内存带宽隔离上的差异。
- 端到端映射：如何从 kernel 级 slowdown 预测推导到服务级 SLO（包括排队、CPU 路径、数据搬运、batching）？
- 在线学习或模型更新策略：在负载变化、新 kernel 出现、硬件代际变化时如何维护预测精度。
- 调度器开销：单次预测和调度决策的耗时，以及高 kernel 提交速率下是否可扩展。
- 对更广泛 GPU 工作负载（如 LLM decoding、训练 kernel、多任务混合）和更长时段运行时的鲁棒性。
- 成本分析的量化结果：在什么条件下 GPU sharing 能真正降低部署成本，什么条件下会因过度节流而抵消收益。

## 元数据与链接

- **标题**：Mosaic: GPU Sharing with Latency Guarantees through Kernel-Level Interference Prediction
- **作者**：Foteini Strati, Ethan Graham, Leo Stephan, Paul Elvinger, Ana Klimovic
- **来源**：arxiv
- **Venue**：arXiv cs.DC
- **DOI**：N/A
- **原文链接**：http://arxiv.org/abs/2610.07504v1
- **PDF 链接**：https://arxiv.org/pdf/2610.07504v1
- **匹配主题**：os-kernel, systems
- **相关性分数**：10

**注意**：本总结基于提供的元数据、摘要和开放 PDF 正文摘录；由于正文摘录不完整，部分系统和实验细节无法确认，已明确标注为“原文摘录/摘要未提供足够信息”。
