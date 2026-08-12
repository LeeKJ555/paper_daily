## 论文针对什么问题

该数据集条目服务于一个系统研究问题：在三个 Linux Kernel 子系统中度量企业层面的“Corporate Truck Factor”，即关键知识在少数公司/组织中的集中程度。要可靠度量这种公司级知识集中，需要比 commit 或文件级归属更细的 token 级作者归属数据。

摘要说明，这是论文《The Corporate Truck Factor: Firm-Level Knowledge Concentration in Three Linux Kernel Subsystems》(VEM 2026) 的配套数据集。选择 `amdgpu`、`net`、`iio` 三个子系统，是为了覆盖不同的企业集中度谱系。

## 提出了什么解决方案

公开三个 Linux Kernel 子系统的匿名化 cregit token 级作者归属数据库：

- `amdgpu`：`drivers/gpu/drm/amd`
- `net`：`net`
- `iio`：`drivers/iio`

每个子系统交付标准 cregit 4 文件 SQLite 集合：

- `blobmap.db`
- `cregit.db`
- `original.db`
- `persons.db`

该数据集作为上述 VEM 2026 论文的 companion dataset。

## 具体是怎么做的

摘要给出的生成方法如下：

- 使用 cregit，即 German 等人提出的 token 级作者归属方法。
- 基于 Linux Kernel 自 2005 年迁移到 git 以来的完整 git 历史生成。
- 覆盖约 12.6M 个存活内容 token，约 4,600 个源文件。
- 每个子系统包含标准 cregit 4 文件 SQLite 集合：`blobmap.db`、`cregit.db`、`original.db`、`persons.db`。
- 所有数据库通过 `PRAGMA quick_check = ok` 完整性检查。
- 更多说明见 `MANIFEST.txt`。

摘要未提供以下实现细节：cregit 具体版本、git 历史截止 commit/日期、kernel 版本、token 过滤规则、匿名化具体策略等。由于开放 PDF 正文摘录为 N/A，无法进一步补充。

## 取得了什么效果

从数据集本身看，摘要给出了以下结果：

- 覆盖三个子系统，约 12.6M 个存活内容 token，约 4,600 个源文件。
- 所有 SQLite 数据库通过 `PRAGMA quick_check = ok` 完整性检查。
- 三个子系统被选择以跨越企业集中度谱系，可支撑企业级知识集中度分析。

但摘要和可用信息中未提供下游论文的具体实验指标，例如各子系统的企业级 Truck Factor 数值、集中度变化、跨子系统对比结论等。因此，关于研究层面的定量效果，原文摘录/摘要未提供足够信息。

## 旁观者视角的问题与不足

- **“匿名化”粒度不明**：摘要称数据库为 anonymized，但标准 cregit 输出包含 `persons.db`，通常与作者身份相关。摘要和当前可获得的正文摘录都没有说明匿名化是在 `persons.db` 中移除或哈希身份，还是仅去除公司信息。这会影响数据可审计性和隐私理解。
- **子系统代表性有限**：仅选择 `amdgpu`、`net`、`iio` 三个子系统，且选择目标明确是为了覆盖企业集中度谱系。对 Linux Kernel 整体或其他子系统的企业级知识集中度不具备广泛代表性。
- **“surviving content tokens”范围未定义**：12.6M 存活内容 token 没有说明总 token 量、是否排除注释/字符串/自动生成代码、空行等。后续比较时可能难以判断覆盖率和可比性。
- **可复现信息不足**：摘要未提供 git 历史截止日期或 commit、cregit 版本、生成参数、是否包含构建脚本或原始 git 镜像。仅有 `MANIFEST.txt` 提示，但正文摘录为 N/A，无法确认其中是否包含这些信息。
- **数据完整性验证较简单**：仅报告 `quick_check = ok`，没有提供更深入的 schema 一致性、token 归属准确性或与上游 git 历史对账结果。

## 值得继续追踪的点

- 配套论文《The Corporate Truck Factor: Firm-Level Knowledge Concentration in Three Linux Kernel Subsystems》(VEM 2026) 发布后，应关注其企业集中度度量方法、三个子系统的实证差异以及治理含义。
- `MANIFEST.txt` 中的具体字段说明、匿名化策略、生成日期、commit 范围和数据库 schema。
- cregit 在此数据集上的参数设置与增量更新方法，以及是否可以扩展到更多 Linux Kernel 子系统或不同版本。
- 企业级 Truck Factor 在大型开源内核项目中的时间演变、维护风险，以及公司之间知识转移对集中度的影响。

## 元数据与链接

- **标题**：The Corporate Truck Factor: anonymized cregit token-authorship databases for three Linux Kernel subsystems (amdgpu, net, iio)
- **作者**：Ellian Carlos Costa, Arthur Pilone, Paulo Meirelles
- **来源**：openalex
- **Venue**：Zenodo (CERN European Organization for Nuclear Research)
- **DOI**：10.5281/zenodo.21302468
- **原文链接**：https://doi.org/10.5281/zenodo.21302468
- **PDF 链接**：https://doi.org/10.5281/zenodo.21302468
- **匹配主题**：os-kernel
- **相关性分数**：15
