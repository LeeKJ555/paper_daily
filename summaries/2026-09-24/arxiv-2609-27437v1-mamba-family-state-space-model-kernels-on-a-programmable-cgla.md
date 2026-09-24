## 论文针对什么问题

边缘与嵌入式推理受功耗和数据移动限制。Mamba 家族状态空间模型用序列线性递归替代注意力，但其推理路径并不是单一的 GEMM kernel，而是混合了多类负载：长 reduction 的 dense projection、短 reduction 的 SSD kernel、以及顺序依赖的 recurrent-state update。

从硬件角度看，关键问题不是“一个 SSM 层是否等于一个加速器 kernel”，而是这些 kernel 在 reduction 长度、流水线占用、数据移动和递归依赖上差异很大。已有工作多为 Mamba 专用 FPGA/ASIC 加速器，而本文关注的是：在不使用固定功能 SSM 数据通路的前提下，可编程 CGLA 栈能否承载这些 kernel，哪些阶段适合流水线，哪些阶段会受短 reduction、kernel 边界或 decode 阶段 projection GEMV 限制。

## 提出了什么解决方案

本文不在模型或数据通路上做专门优化，而是将 Mamba 家族主要 kernel 组映射到 IMAX 这一可编程 CPU-Grounded Linear Array（CGLA）上，复用同一套执行栈，把 projection、SSD Step-1、recurrent-state update 和 token generation 全部放在同一可编程流水线上运行。

论文的定位是可编程 CGLA 上的诊断研究：通过从 kernel 执行到 token-level integration 的测量，区分哪些 Mamba 阶段适合长 reduction 流水线，哪些阶段需要 boundary reduction 和 persistent-weight execution，而不是提出一个系统级加速方案。

## 具体是怎么做的

IMAX 是一种 CPU-Grounded Linear Array，将主机 CPU 与一维流式处理单元（PE）和局部存储模块（LMM）流水线耦合。实验在 IMAX FPGA 原型上实现 Mamba-2 的主要 kernel 组，并用 ARM Cortex-A72 软件路径作为正确性和 CPU 时序参考。

Mamba-2 层被拆成三类 kernel shape：

- **in-proj / out-proj**：dense GEMM，reduction length 为 1024/2048，属于长 reduction，适合深度流水线占用；
- **SSD Step-1**：GEMM1 + GEMM2，reduction length 为 N、Q 且不超过 128，属于短 reduction，受 setup cost 主导；
- **Step-3**：MV recurrence，N=128，具有序列依赖。

关键实现细节包括：

- 对 SSD Step-1 的 Hadamard mask，实现了 `imax_hadamard()`，在 IMAX 内部完成 `R ← R ⊙ Λ`，避免 GEMM1 写回 DRAM、CPU 做 mask、GEMM2 再读回的 DMA round trip；
- 每个调用处理一行 M1×Q 结果矩阵，使用两个并行 OP_FML lane，每迭代处理 Q/2 个元素对，算术强度约 0.25 FLOP/byte；
- 通过将 outer batch 设为 `M1 = Nheads × Q`，摊薄短 reduction 的 per-launch 开销。

测量维度包括 IMAX execution time、DMA-inclusive total time、ARM Cortex-A72 软件参考时间，以及 token-level integration 行为。所有 kernel 使用 FP32。Projection kernels 取三次运行均值，DMA-inclusive min-max spread 低于 0.1%；Step-1 和 token generation 为代表性运行，未报告置信区间。层特征实验使用 Mamba-370M，token generation 实验使用 Mamba-130M，层组合时序采用 T=120、Q=60。

## 取得了什么效果

论文报告了以下主要结果：

- **Projection kernels 与 IMAX 长 reduction 流水线匹配**，说明 dense projection 是可编程 CGLA 适合的负载。
- **SSD Step-1 受短 reduction 和 kernel-boundary overhead 限制**，未融合的 Step-1 路径在 boundary transfers 之后比 ARM 软件参考更慢。
- **Mamba-130M token-level integration 显示 decode 瓶颈是 projection GEMV**：in-proj 占 decode 时间的 66.8%，out-proj 占 32.7%，其余阶段均低于 0.3%。
- 单 lane Mamba-130M 达到 **0.345 tokens/s**，并保持 ARM 参考的 greedy token 序列。
- 论文明确表示，token run 没有匹配的端到端吞吐基线；DMA-inclusive 执行和 kernel-boundary overhead 限制了 FPGA 原型，因此该工作属于适用性和瓶颈诊断，不是系统级加速证明。
- FP32-only 评估和仅核心 ASIC 模型不支持 reduced-precision 或板级能耗结论。

原文摘录/摘要未提供各 kernel 相对 ARM 参考的绝对加速比或逐 kernel 绝对执行时间，主要给出上述定性结论与 token-level 指标。

## 旁观者视角的问题与不足

- **缺乏端到端匹配基线**：0.345 tokens/s 的 token throughput 没有同系统 CPU 端到端基线做对比，因此很难判断可编程 CGLA 相对软件路径的实际收益；尤其是未融合的 SSD Step-1 已经慢于 ARM reference，说明 DMA 和 kernel-boundary 开销可能抵消计算阶段的优势。
- **精度范围过窄**：全部实验仅使用 FP32，未覆盖边缘部署常见的 INT8/FP16 等低精度路径，无法回答低精度下的性能、面积或能耗收益。
- **ASIC 模型不能支撑系统级结论**：ASIC 数据来自 28nm 核心综合，排除了主机 CPU、DDR、DMA 和板级组件，不能外推到系统能效；论文自身也承认这一点。
- **统计可信度有限**：只有 projection kernels 有三轮均值和 spread，Step-1 与 token generation 只是代表性运行，没有置信区间，难以评估波动。
- **SSD 路径尚未完整优化**：Hadamard 与 GEMM2 仍未融合，kernel-boundary 开销依然存在；decode 阶段 projection GEMV 瓶颈也未通过 persistent-weight execution 得到缓解。
- **单 lane 结果难以外推**：0.345 tokens/s 的低吞吐出现在单 lane 配置下，论文没有给出多 lane、更宽 row grouping 或更大 batch 下的扩展数据，因此 CGLA 的实际潜力尚不清楚。

## 值得继续追踪的点

- **Fused Step-1 / Hadamard–GEMM2 融合**：消除中间 DMA round trip 和 kernel-launch 边界开销，降低 SSD Step-1 的固定成本。
- **Persistent-weight execution**：在 decode 阶段保持 projection weights 驻留，减少重复权重加载，直接缓解 projection GEMV 瓶颈。
- **Wider row grouping / 更大 outer batch**：进一步摊薄短 reduction kernel 的 setup cost。
- **低精度评估**：增加 FP16/INT8 等精度路径，并与匹配的系统级 baseline 对比，验证低精度对性能和能耗的影响。
- **多 lane / 更大 PE 阵列扩展**：考察单 lane 诊断结果能否通过扩展片内并行度改善 token throughput，并同时报告 DMA-inclusive 端到端数据。
- **与专用 Mamba 加速器的归一化对比**：在完整系统边界和能耗模型下，比较可编程 CGLA 与 LightMamba、FastMamba、MARCA、EpochCore 等专用设计的优劣。

## 元数据与链接

- **标题**：Mamba-Family State-Space Model Kernels on a Programmable CGLA  
- **作者**：Takuto Ando, Yasuhiko Nakashima  
- **来源**：arXiv  
- **Venue**：arXiv cs.AR  
- **DOI**：N/A  
- **匹配主题**：os-kernel  
- **相关性分数**：9  
- **原文链接**：http://arxiv.org/abs/2609.27437v1  
- **PDF 链接**：https://arxiv.org/pdf/2609.27437v1
