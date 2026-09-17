## 论文针对什么问题

论文关注多租户 LLM 推理服务中的性能隔离问题。LLM 服务通常以共享、多租户方式提供，以提高 GPU 利用率并分摊基础设施成本。多租户场景下，某个客户端的高负载工作流（例如高请求率、大量 prompt/completion token）可能占满共享 GPU 资源，导致其他客户端的延迟 SLO 被违反。现有方案例如排队公平、批处理公平，通常只在长期吞吐量上让客户端均等，但无法提供 token 级延迟隔离保证。因此，行为良好的客户端仍可能在 token 级延迟上受到显著干扰。

论文用表 1 展示了这一干扰：在 Plain SGLang、VTC、DLPM 等系统上，TTFT、TBT、TTLT 等指标出现数十倍性能退化，而 FairInference 能将延迟保持在接近隔离执行的水平。

## 提出了什么解决方案

论文提出了 **FairInference**，这是首个为 LLM 推理服务提供延迟隔离保证的系统。其核心是一种新的公平性定义：**δ-token fairness**。

该保证的含义是：对于一个行为良好的客户端，如果某个 token 在隔离执行中需要 d 个时间单位生成，则在多租户执行中该 token 应在 d + δ 个时间单位内生成。其中 δ 是管理员配置的最大可容忍延迟增量。该定义同时覆盖 TTFT（首 token 延迟）、TBT（token 间延迟）和 TTLT（总 token 延迟）等 token 级延迟指标。

FairInference 的关键设计目标是：在缺少细粒度 GPU 调度或资源分配支持的情况下，限制共享 GPU 资源带来的延迟。系统通过为每个 token 设置 deadline，并对 GPU 计算共享造成的延迟进行约束，同时考虑共享 KV cache 在 GPU 内存中引入的额外延迟。

## 具体是怎么做的

根据论文正文摘录，FairInference 的设计包含以下要点：

1. **δ-fairness 定义与 deadline 推导**  
   对请求中的每个 token k，系统会为其分配一个 deadline d<sub>k</sub>：  
   d<sub>k</sub> = TISO<sub>k</sub> + δ  
   其中 TISO<sub>k</sub> 是该 token 在隔离执行中的完成时间，δ 是管理员配置的延迟容忍上限。系统必须保证即使在多租户争用下，也没有 token 超过其 deadline。

2. **隔离执行与公平资源份额假设**  
   推导这些 deadline 需要假设：在隔离执行中，每个客户端运行在专用的公平资源份额上，例如系统资源的 1/N。这一假设用于计算 token 的原始完成时间 TISO<sub>k</sub>。

3. **解决 LLM 推理的特殊挑战**  
   LLM 推理 pipeline 通常分为两个阶段：计算密集的 prefill 阶段和内存密集的 decode 阶段。多租户共享 GPU 时，prefill 和 decode 可能相互干扰。FairInference 需要在没有细粒度调度或资源分配支持的情况下，约束共享 GPU 计算带来的延迟。

4. **调度器执行 per-token deadlines**  
   FairInference 的调度器强制每个 token 的 deadline，限制 GPU 计算共享造成的延迟，并将共享 KV cache 引入的额外延迟纳入考虑。论文提到系统使用性能建模来推导 per-token deadlines，并针对共享 KV cache 的延迟进行调整。

5. **与其他 δ-fair 系统的可组合性**  
   论文还简要讨论了 FairRAG 系统，即把 FairInference 与 FairDB 组合，用于 LLM 推理调用加数据库请求的场景。组合后的延迟上界可以视为各组件 δ 的叠加，但论文明确指出这一组合性质将在未来工作中评估。

## 取得了什么效果

论文声称 FairInference 有效限制了行为良好客户端的 token 级延迟峰值，并在总吞吐量上相比最先进的 LLM 推理系统有所提升。具体来看：

- 在论文表 1 中，FairInference 将 TTFT、TBT、TTLT 分别保持在约 3.2s、47ms、5.3s，相对隔离执行为 1×；而 Plain SGLang、VTC、DLPM 分别出现最高 66×、28×、32× 的 TTFT 退化，以及 TBT/TTLT 的数倍到数十倍退化。
- 论文第 7 节评估部分提到，FairInference 在 δ=3s 的配置下，能够将行为良好客户端的 token 级延迟（TTFT、TBT、TTLT）限制在相对隔离执行不超过 δ 的范围内，且独立于其他客户端的负载。
- 摘要提到 FairInference “improves overall throughput compared to state-of-the-art LLM serving systems”。但原文摘录和摘要未提供具体吞吐量对比数据、实验配置、模型规模或负载细节。因此除表 1 所列延迟干扰数据外，其他实验细节信息不足。

## 旁观者视角的问题与不足

1. **实验细节披露有限**  
   论文摘要和当前可见正文摘录没有给出完整的实验设置，例如 GPU 型号、模型规模、客户端数量、请求到达模式、δ 的具体取值依据、对比基线的版本和配置等。表 1 只展示了延迟干扰的倍数，缺乏吞吐量改善的量化数据，难以判断系统在不同负载下的实际收益。

2. **对隔离执行模型的依赖较强**  
   δ-token fairness 的 deadline 建立在“隔离执行中每个客户端使用 1/N 公平资源份额”这一假设上。如何准确、低成本地获得每个 token 的 TISO 时间，以及该假设在动态负载、异构请求长度、不同硬件配置下是否成立，论文可见部分没有充分说明。如果隔离时间模型本身不准，deadline 和公平保证可能失效。

3. **系统实现与调度机制的细节不完整**  
   从可见摘要和正文摘录看，FairInference 如何“在没有细粒度调度或资源分配支持的情况下”实际执行 per-token deadline、如何进行性能建模、如何处理 prefill 与 decode 争用、如何管理 KV cache 延迟补偿，目前提供的信息比较粗略，缺少机制层面的伪代码或系统架构图。

4. **与现有系统的比较范围有限**  
   表 1 仅比较了 Plain SGLang、VTC、DLPM 三种系统，且以延迟干扰为主。没有展示在吞吐量、尾延迟、SLO 达成率等指标上与更多最新 LLM serving 系统的完整对比。此外，FairRAG 的可组合性只做了概念讨论，未提供实验结果。

5. **潜在的开销与可行性风险未展开**  
   为每个 token 设置 deadline 并进行调度和 KV cache 延迟补偿，可能引入额外的计算和内存开销。论文可见部分没有讨论这些开销对系统吞吐量和 GPU 利用率的影响。如果没有细粒度抢占或资源隔离机制，单纯依赖 deadline 调度可能在某些高争用场景下无法严格执行。

## 值得继续追踪的点

- **FairInference 的具体调度算法与性能建模方法**：如何精确估计每个 token 的隔离完成时间，以及如何在不依赖细粒度 GPU 调度的情况下强制执行 per-token deadline。
- **组合 δ-fair 系统的评估**：论文提到未来将评估 FairInference 与 FairDB 等系统的组合性质，这关系到跨 LLM 推理和外部数据访问的端到端延迟隔离。
- **不同模型规模与硬件平台上的泛化性**：在更大模型、多 GPU、不同 prefill/decode 负载比例下，δ-token fairness 是否仍然成立。
- **吞吐量改善的量化证据**：论文声称改善了总吞吐量，但具体数据尚未披露。后续发布版本或完整论文中是否包含与 vLLM、TensorRT-LLM 等系统的吞吐量和尾延迟对比。
- **δ 参数的自适应或自动配置**：δ 目前是管理员配置的固定值，如何根据客户端 SLO、负载动态调整 δ，以及 δ 对系统利用率的影响。
- **生产环境中的鲁棒性与故障恢复**：在高争用或资源过载情况下，FairInference 能否继续保持 token 级延迟上界，以及如何处理超时或不可行的 deadline。

## 元数据与链接

- **标题**：Token Latency Fairness: Performance Isolation for Multi-Tenant LLM Serving  
- **作者**：Dev Bali, Soujanya Ponnapalli, Yichuan Wang, Natacha Crooks, Scott Shenker, Matei Zaharia  
- **来源**：arXiv  
- **Venue**：arXiv cs.DC, cs.LG  
- **DOI**：N/A  
- **原文链接**：[http://arxiv.org/abs/2609.18112v1](http://arxiv.org/abs/2609.18112v1)  
- **PDF 链接**：[https://arxiv.org/pdf/2609.18112v1](https://arxiv.org/pdf/2609.18112v1)  
- **匹配主题**：os-kernel, systems  
- **相关性分数**：10
