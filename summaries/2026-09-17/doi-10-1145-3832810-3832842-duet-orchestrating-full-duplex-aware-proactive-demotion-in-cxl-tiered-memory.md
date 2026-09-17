由于给定摘要与正文摘录均为 N/A，以下总结只能依据标题、元数据给出有限说明；论文内部的问题定义、系统设计、实验与结论均无法从现有信息中获取。

## 论文针对什么问题
原文摘录/摘要未提供足够信息。  
从标题看，论文可能涉及 CXL tiered memory 中的内存数据降级（demotion）问题，尤其是如何在全双工（full-duplex）特性下进行主动降级编排；但具体研究动机、问题范围和目标无法确认。

## 提出了什么解决方案
原文摘录/摘要未提供足够信息。  
标题中的 “Duet” 可能是所提出方案或机制的名称，暗示一种 full-duplex-aware 的 proactive demotion 编排方法；但其系统架构、算法或接口未提供。

## 具体是怎么做的
原文摘录/摘要未提供足够信息。  
无法描述关键机制、工作流程、数据结构、预测/降级策略或系统实现细节。

## 取得了什么效果
原文摘录/摘要未提供足够信息。  
没有提供实验设置、基准、性能提升、能耗、尾延迟或其他评估指标。

## 旁观者视角的问题与不足
由于没有摘要和正文，无法对论文的实际设计、实验或局限性做具体评判。  
仅从标题和元数据可提出开放性问题，例如：full-duplex-aware 是否准确建模了 CXL 全双工带宽竞争；proactive demotion 是否会引入过高的预测或迁移开销；评估中是否覆盖足够多的 tiered-memory 场景与对比基线。这些问题只是基于标题的疑问，不代表论文实际存在这些不足。

## 值得继续追踪的点
原文摘录/摘要未提供足够信息。  
若获取全文，建议关注：1）CXL tiered memory 中的主动 vs. 被动降级策略；2）full-duplex 感知如何影响 demotion 决策；3）与现有 tiered-memory 系统或硬件方案的对比评估；4）在真实 CXL 设备或模拟平台上的实验结论。

## 元数据与链接
- 标题：Duet: Orchestrating Full-Duplex-Aware Proactive Demotion in CXL Tiered Memory
- 作者：Shengsong Kong, Lizhao Zhang, 何书范, Zhenzhou Ji, Zhongchuan Fu, Malik Saad Nawaz, Yifan Wan, Yue Yu, Yu Feng Zheng, Tianyu Hu, Kim Jei, Yufa Yang
- 来源：openalex
- Venue：N/A
- DOI：10.1145/3832810.3832842
- 原文链接：https://doi.org/10.1145/3832810.3832842
- PDF链接：https://doi.org/10.1145/3832810.3832842
- 匹配主题：tiered-memory
- 相关性分数：12
