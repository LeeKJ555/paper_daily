## 论文针对什么问题

该工作是对 Luo 和 Wei 论文中一个计算机辅助结论的**独立、部分核验**，不是反驳，也不是完整验证。

Luo 和 Wei（arXiv:2610.31456）证明：对于单位密度点电荷，在屏蔽库仑/Yukawa 排斥势 \(e^{-\kappa r}/r\) 下，所有三维晶格中：

- 当 \(\kappa < \kappa^*\) 时，体心立方（BCC）晶格能量最小；
- 当 \(\kappa > \kappa^*\) 时，面心立方（FCC）晶格能量最小；
- 临界值 \(\kappa^* \approx 1.7179218684699\)。

本工作试图独立检查的是该证明中**计算机辅助有限部分**：已验证的打印数字、不等式和若干 Lean 形式化陈述是否成立，是否存在差异。摘要明确表示，检查结果不是对 Luo-Wei 定理 1.1 的验证，也不是驳斥。

另外，元数据显示匹配主题为 `os-kernel`，相关性分数为 9，但论文内容实际属于计算物理/数学形式化验证，并非操作系统或内核方向，这一点存在明显分类不匹配。

## 提出了什么解决方案

作者提出了一个**分层核验方案**，而不是重新证明完整定理。该方案把可检查内容分为若干层级，并配合阳性和阴性对照：

- **Tier A**：用 Lean 4.34.1 对部分引理做形式化 kernel 检查；
- **Tier L**：直接采用原论文的陈述，按原文原样处理；
- **Tier C**：用 Arb ball arithmetic 和多种独立数值方法复算临界值 \(\kappa^*\) 及部分引理；
- **Tier X**：记录 IEEE 双精度数值和仓库 guard 输出。

同时设计了：

- **阳性对照**：三种方法复现 \(\kappa^*\)；暴力重新枚举 shell 多重数；
- **阴性对照**：故意植入错误 multiplicity、篡改表项、cell bound、`sorry` 和 `axiom`，观察 kernel 或 axiom audit 是否能拒绝。

该方案还明确列出“未做”和“限制”，例如哪些部分未进入 Lean、哪些未重跑、哪些测试未通过，以此划定可信边界。

## 具体是怎么做的

### Tier A：Lean 形式化 kernel 检查

- 使用 Lean 4.34.1，Mathlib 固定在特定版本；
- 公理范围限定在 `propext`、`Classical.choice`、`Quot.sound`；
- `leanchecker` replay 返回码为 0；
- 模块包括：`Basic`、`Shells`、`Chains`、`LemmaA5`、`Lemma61`；
- 由生产者和独立 AI 审计分别在私有重建、字节相同的 `.olean` 文件上重放；
- 五个模块的全部 138 个声明打印出的公理仅为上述三个；
- **没有人工审计，没有 statement lock**。

17 个 Lean 定理/语句中包含：

- 10 个实质性定理；
- 7 个单行有理数事实或桥接引理；
- `lemma61_prop41_bracket` 是一个 for-all-x 不等式，不是有限语句。

这些 Lean 形式化覆盖了：

- FCC shell multiplicities \(N_1..N_{12}\) 和 17 个非零 BCC multiplicities \(M_l\)，\(l \le 48\)，并证明它们等于在 \(\mathbb{Z}^3\) 上的计数；
- Lemma A.5、A.6、A.7、A.8 的实数版本，涉及 `Real.pi` 和 `Real.exp`；
- Lemma 6.1 证明中的常数和尾部；
- Lemma A.6 的有理尾部；
- Lemma A.1 的有理步骤。

多个 Lean 语句**弱于原论文打印版本**：

- `exp_fcc_21` 仅在 \(t = 21/10\) 处检查；
- `prop41_bracket` 仅检查有理 bracket；
- `tail_*` 只检查有理 majorant 的部分和；
- `lemmaA5_*` 通过 `*_eq_ncard` 引理与 box counts 连接。

### Tier C：Arb ball arithmetic 与独立复算

Arb ball arithmetic 用于检查：

- Lemma A.6 在 \(\kappa = 1.717921868469903\) 和 \(\kappa = 1.717921868469904\) 以及邻近控制点的 \(G = 2(E_B - E_F)\) 符号；
- Lemma A.5 的最小 slack：\(7.52 \times 10^{-4}\) 和 \(7.65 \times 10^{-5}\)；
- Lemma A.1 和 Lemma A.3。

\(\kappa^*\) 有三种独立复现：

1. 320-bit Arb Ewald sums；
2. 直接实空间 Arb sum；
3. 对论文积分方程 (1.4) 的 40 位 mpmath quadrature。

结果：

- (E) 和 (Q) 与论文全部 25 位打印数字一致；
- (D) 的区间包含 (E) 和 (Q)；
- 审计增加第四种方法：经典 Ewald split，使用自由分裂参数，70 位精度，得到：
  \[
  1.71792186846990386425087416660628171879468538
  \]
- 独立 `python-flint 0.9.0` 复现了 Lemma A.6 的两个符号。

IEEE 双精度直接求和只能达到约 11 位；`float64` Ewald 约 12 位，无法解析宽度为 \(10^{-15}\) 的 enclosure。

### Tier X：双精度与 guard 输出

记录 IEEE 双精度值和仓库 guard 输出。

### 阳性和阴性对照

**阳性对照**：

- 三种 \(\kappa^*\) 复现；
- shell counts 被暴力重新枚举。

**阴性对照**：

- 植入错误 multiplicity \(N_7 = 46\)、篡改表项和篡改 cell bound，均被 kernel 拒绝，返回码 1；
- witness 文件显示 kernel 将篡改检查判为 `false`，并将 \(N_7\) 判为 48；
- 植入 `sorry` 和植入 `axiom` 虽然可以编译，但被 axiom audit 捕获。

### Lemma A.3/A.4 的检查

三个指数边界约以 \(2 \times 10^{-16}\) 的余量成立；端点采用向外舍入，安全方向上分子分别超出精确对数 4.2、1.05、2.5 个单位；\(11/25\) 和 \(147/1000\) 是带 slack 的中间有理数；只有 beta 的边界是紧的。摘要判断这不是错误。

### 未完成的工作

- Lemma 6.1 的组装未进入 Lean，包括：
  - theta 函数作为 lattice sums；
  - Poisson summation 推出 \(D(1) = 0\)；
  - 对所有 \(n\)，\(N_n < 30n\)；
- Lemma A.4（5,828 个矩形）和 Lemma A.2 未重跑，因为 partition data 没有公开；arXiv 未列出 ancillary files，作者计划向 Luo 和 Wei 请求数据；
- Lemma A.6 未在 Lean 中形式化，因为 pinned Mathlib 中没有 `erfc`。

### 运行与审计状态

- 由 AI agents（Claude）在作者指导下产生；作者对内容负责；
- 独立 AI 审计结论为 `ACCEPT_WITH_CORRECTIONS`，无 blocking item；审计重建五个模块并用 `leanchecker` 重放，返回码 0；
- 但 Tier A 没有人工审计，没有 statement lock；
- Lean 运行与另一进程共享 core，两次早期编译被杀，可能是内存不足；
- 仓库 guard `antigravity_guard.py`、`test_rigor_guard.py` 和 `pytest tests/` 因其他 lane 文件的已有原因而失败，作者未声称它们通过；
- Elenchus ledger gate 退出码为 1：0 个 blocking findings，8 个 `LEDGER_UNAUDITED_TIER_A` flags，每个 Tier A 行一个；这些 flags 保留，因为没有人类认证相关 glosses；AI 审计重跑 gate 得到相同结果。

## 取得了什么效果

- 所有能检查的打印数字和不等式都成立，未发现差异；
- 17 个 Lean 语句/定理被 kernel 检查，覆盖了 shell multiplicities、部分 A 系列引理、Lemma 6.1 的有理尾部等；
- \(\kappa^*\) 被三种独立方法复现，并增加了一个 70 位精度值；
- 阴性对照被正确拒绝，说明 kernel 检查和 axiom audit 对植入错误具有区分能力；
- 但该工作明确不是 Luo-Wei Theorem 1.1 的完整验证，也不是反驳；它只覆盖计算机辅助证明的有限部分。

摘要也指出该工作关注的是“点电荷在晶格上的屏蔽库仑排斥模型”，不是真实材料。

## 旁观者视角的问题与不足

1. **Lean 覆盖范围有限且存在弱化**：多个 Lean 语句弱于打印版，例如 `exp_fcc_21` 只在单点 \(t=21/10\) 检查，`prop41_bracket` 只检查有理 bracket，`tail_*` 只看有理 majorant 的部分和。这意味着即使这些 Lean 定理通过，也不能等价于原论文对应陈述的完全形式化验证。

2. **没有 statement lock、没有人工审计**：AI 审计结论是 `ACCEPT_WITH_CORRECTIONS`，虽然无 blocking item，但其中的 “corrections” 未展开说明。没有 statement lock，意味着 Lean 陈述与原始打印数学陈述之间可能存在语义层面的漂移，机器重放通过不等于语义等价。

3. **关键组装未形式化**：Lemma 6.1 的组装，包括 theta 函数、Poisson summation 和 \(N_n < 30n\)，未进入 Lean。这是连接有限引理与整体结论的重要环节。此外，Lemma A.4 因 partition data 不公开而无法重跑，A.2 也未重跑，进一步削弱了复现完整性。

4. **运行环境不够干净**：Lean 运行与其他进程共享 core，两次编译被杀，可能是 OOM。仓库 guard 和 pytest 均未通过。虽然作者将失败归因于其他 lane 的已有问题，但从可复现性角度看，工程可靠性尚未完全达标。

5. **数值验证对精度极度敏感**：双精度只能到 11–12 位，无法解析 \(10^{-15}\) 宽度的 enclosure。这说明该问题无法用普通浮点验证，必须依赖 Arb/mpmath 等高精度工具；也意味着任何低精度复现都不可信。

6. **账本 gate 仍处于未认证状态**：Elenchus ledger gate 退出码为 1，8 个 `LEDGER_UNAUDITED_TIER_A` flags 未清除，因为没有人类认证 glosses。机器检查可重放，但语义审计尚未完成。

7. **元数据分类存疑**：本记录匹配主题为 `os-kernel`，相关性分数 9，但论文内容是数学物理+形式化验证，不是操作系统或内核。该分类可能误导系统方向的检索与读者预期。

8. **摘要中 arXiv 编号异常**：摘要给出的 Luo-Wei 预印本编号为 `arXiv:2610.31456`，其形式异于常见 arXiv 编号，需读者自行核对；本总结仅按摘要照录。

## 值得继续追踪的点

- 作者计划向 Luo 和 Wei 请求 partition data，若能获得，则可重跑 Lemma A.4（5,828 个矩形）和 Lemma A.2；
- Lemma 6.1 的 theta 函数、Poisson summation、\(N_n < 30n\) 组装是否能进入 Lean；
- 若 Mathlib 加入 `erfc`，是否能将 Lemma A.6 形式化；
- Tier A 的 8 个 `LEDGER_UNAUDITED_TIER_A` flags 是否会通过人工审计和 statement lock 清除；
- AI 审计中 `ACCEPT_WITH_CORRECTIONS` 的具体 corrections 是什么；
- 后续是否会出现真正的人类审计，或至少对 Tier A glosses 的独立人工认证；
- Luo-Wei 论文或作者是否会公开 ancillary files，以改善可复现性；
- 该条目的元数据主题是否应修正为计算物理/形式化数学，而非 `os-kernel`。

## 元数据与链接

- **标题**：An independent partial check of the three-dimensional Yukawa bcc-to-fcc threshold of Luo and Wei: the threshold reproduced three ways, seventeen Lean statements kernel-checked, and what remains open  
- **作者**：Xavier Callens  
- **来源**：openalex  
- **Venue**：Zenodo (CERN European Organization for Nuclear Research)  
- **DOI**：10.5281/zenodo.23708331  
- **原文链接**：https://doi.org/10.5281/zenodo.23708331  
- **PDF 链接**：https://doi.org/10.5281/zenodo.23708331  
- **匹配主题**：os-kernel  
- **相关性分数**：9  
- **开放 PDF 正文摘录**：N/A（未能获取额外正文）
