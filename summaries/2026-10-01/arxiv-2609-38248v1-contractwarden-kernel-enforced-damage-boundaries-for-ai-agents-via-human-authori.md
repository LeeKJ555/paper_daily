## 论文针对什么问题

LLM Agent 已经能够执行命令、创建子进程、直接访问文件和网络。因此，间接提示注入、恶意工具输出或规划错误都可能转化为操作系统层面的副作用。

应用层校验在面对“一个被接受的工具调用会展开成 shell、解释器、原生二进制、子进程、临时文件和直接系统调用”时并不充分。论文认为连续执行安全边界面临三个主要缺口：

- **进程创建后附加策略存在竞态**：不可信代码可能在策略注册前运行。
- **进程树继承会漏掉横向传播**：文件、管道、FIFO、Unix-domain socket 等 IPC/持久对象可能传递安全状态，只跟踪进程树不够。
- **只检查网络连接建立不够**：连接可能在进程读取敏感数据前已经建立，受限 Agent 可以通过看似不受限的载体“洗白”安全状态。

因此论文要解决的核心问题是：如何让操作系统在不可信任务开始前，持续执行一个人工授权的资产损害边界。

## 提出了什么解决方案

论文提出 **ContractWarden**，一个 Linux 参考监视器/reference monitor。它强制执行人工授权的 damage boundary，不信任 Agent 或其策略建议。

核心方案可以概括为：

- 模型只提议一个**三态资产合约**：`allow`、`deny`、`no_egress`，但最终选择由人完成。
- 在不可信代码运行前，通过 **execution gate** 把合约绑定到具体任务。
- 使用扩展的 **eBPF LSM** 数据平面强制执行文件和网络决策，并在进程、普通文件、管道、FIFO 和受支持的 Unix-domain socket 之间**单调传播 `no_egress`**。
- 目标不是判断 Agent 计划是否正确，而是把已声明资产上的损害边界降为有界的内核强制动作。

论文把自己的贡献总结为三点：

1. 提出人工授权的 closed-set 资产合约。
2. 提出 gate-before-exec 绑定和对象级单调传播机制，抵抗安全状态洗白。
3. 在 19 项安全属性、4 种配置成本分解，以及虚拟/物理平台上与 frozen ActPlane 的对比中做了评估。

## 具体是怎么做的

### 系统组成与信任模型

系统包含：

- **H**：人类授权者；
- **M**：模型提议者；
- **Aτ**：任务域；
- **C**：特权控制平面；
- **K**：内核执行器。

人类维护一个已声明资产集合 **R**。对任务 τ，确认后的合约是：

\[
\Gamma_\tau: R \to \{\text{allow}, \text{deny}, \text{no\_egress}\}
\]

含义是：

- `allow`：不增加 ContractWarden 限制；
- `deny`：拒绝受支持的文件和命名空间操作；
- `no_egress`：允许本地访问，但阻止获得该状态的载体使用受管网络出口。

每个活动任务获得一个非复用的用户态 UUID，以及一个有界内核位置 `task_id ∈ [0, 63]`，用 source bit \( b_\tau \) 表示。进程或受支持对象 \( x \) 的状态为：

\[
S(x) = \langle L(x), E(x) \rangle
\]

其中 \( L \) 是来源位图，\( E \) 是 egress 拒绝位。状态 join 是单调的：

\[
\langle L_1, E_1 \rangle \sqcup \langle L_2, E_2 \rangle
= \langle L_1 \lor L_2, E_1 \lor E_2 \rangle
\]

不可信部分包括提议者、任务命令、Agent 输入和普通子进程。它们可以 fork、执行原生代码、重命名文件、传递描述符、通过受支持 IPC 中继、在读取受限资产前建立连接，以及尝试复用标识符。可信部分包括内核、BPF/LSM 路径、特权控制平面和人类最终输入。任务本身没有 root 或内核管理能力。

### 授权与预执行绑定

模型接收资产标识符和元数据，但不一定需要接收规范化本地路径。控制平面把确认动作与本地资产表重新关联，拒绝缺失、重复、未知或超出任务域的动作。

安全上：

- 提议者不能自己授权；
- 人类不会直接修改 BPF map；
- launcher 创建一个阻塞在专用文件描述符上的子进程，获取 `pidfd`，然后通过认证的 Unix `SOCK_SEQPACKET` 通道把 pidfd、任务标识符和合约发送给 daemon；
- daemon 校验策略，并在 socket 创建、连接和发送时执行 egress 检查。

### 数据平面与传播

数据平面使用 eBPF LSM 执行文件与网络决策，并在以下对象之间单调传播 `no_egress`：

- 进程
- 普通文件
- 管道
- FIFO
- 受支持的 Unix-domain socket

设计目标包括六个安全不变量。生命周期方面，任务进程树被放入 cgroup，cgroup 为空后才清理任务策略。但论文也指出，cgroup 为空不能证明持久 inode 或 cgroup 外接收者已经丢弃旧来源位。

因此，有界 source position 在没有 generation tags、完整全局存活计数或保守不重用策略之前，不能安全重用。对象本地存储则使普通任务和 inode 释放独立于 PID 与 inode 编号复用。

### 明确排除的范围

ContractWarden 不尝试证明 Agent 计划正确，也不保护未声明资产，不推断隐式或字节级流，不中介所有 IPC 和设备类型，不防御内核被攻破，也不提供普通任务内 declassification 操作。

## 取得了什么效果

论文给出的评估结果如下：

- **安全测试**：19 项安全测试，共 570 次运行，全部满足预定义的返回值和副作用判据。
- **性能开销**：在三个 collocated file-I/O workload 上：
  - Linux 6.15 虚拟机中 median overhead 为 **11.96–12.89%**；
  - Linux 6.15 物理平台上为 **35.79–61.54%**；
  - 两者都低于评估的 frozen ActPlane baseline。
- **结论**：在已声明资产、受支持路径和受控对象生命周期上，实现了确定性的内核强制执行。

论文还指出，虚拟机和物理机批次的排序一致，但百分比幅度不同。相同固定单次操作工作在更快原生运行时中占比更大，而 guest 还包含 hypervisor 调度，因此只做批次内比较。时间测量覆盖稳态 workload 执行，不包括引擎启动、模型提议和人类确认时间。

## 旁观者视角的问题与不足

从系统研究角度看，这篇论文的边界划分很清楚，但仍有以下具体问题：

1. **保证高度依赖人工输入的完整性**  
   只要资产集合声明不完整，或人类选择了过宽动作，安全保证就会被破坏。论文没有提供机制来验证资产声明是否完整，也没有评估人类决策质量。

2. **物理平台开销明显偏高**  
   物理平台上 35.79–61.54% 的 overhead 比虚拟机高很多。论文虽然给出了方向和解释，但没有提供完整的跨环境归一化数据，也没有端到端包含授权、绑定、模型提议和人类确认的延迟数字。

3. **source position 和 task_id 空间受限**  
   `task_id ∈ [0, 63]` 和 64-bit source bitmap 限制了同时活动的任务/来源数量。论文承认，在没有 generation tags 或全局存活计数前，有界 source position 不能安全重用。这会影响长期运行或高频任务创建场景。

4. **只覆盖部分 IPC 和设备类型**  
   传播路径覆盖普通文件、管道、FIFO 和受支持的 Unix-domain socket，但不覆盖所有 IPC 和设备。对复杂系统而言，未覆盖路径可能成为绕过面。

5. **权限级传播可能过度污染**  
   把“能写”近似为实际影响，可能造成 over-taint，而普通任务代码不能自己去除标签。缺少可信 declassification 会限制可用性。

6. **与 ActPlane 的比较范围有限**  
   论文只比较重叠属性，非重叠语义不当作失败。这虽然合理，但也意味着性能结论不能简单推广为“整体优于 ActPlane”。

7. **缺少用户研究**  
   没有评估可用性、决策时间、alert fatigue 和合约质量问题。这些是实际部署中很重要，但当前实验没有覆盖的部分。

## 值得继续追踪的点

- **可信 declassification 机制**  
  例如 attested transformation 或独立授权释放，如何在不依赖任务代码的情况下安全恢复 egress。

- **source position/task_id 安全重用**  
  generation tags、完整全局存活计数或保守不重用策略的实际实现和开销。

- **扩展传播与中介范围**  
  覆盖更多 IPC、设备类型以及隐式/字节级流，减少未覆盖路径风险。

- **端到端性能评估**  
  将模型提议、人类确认、execution gate、eBPF 安装等成本纳入整体测量，并解释 VM 与物理平台开销差异。

- **资产声明与 usability 研究**  
  用户在真实任务中如何选择 `allow/deny/no_egress`，合约质量如何影响安全结果。

- **生命周期与回收语义**  
  cgroup drainage 与持久 inode、cgroup 外接收者之间的交互，如何避免误清理或漏清理。

## 元数据与链接

- **标题**：ContractWarden: Kernel-Enforced Damage Boundaries for AI Agents via Human-Authorized Contracts
- **作者**：Dongxu Cui, Zhichao Gu, Ping Zheng, Wenshuai Xi, Simeng Han, Yong Liao
- **来源**：arXiv
- **Venue**：arXiv cs.CR, cs.OS
- **DOI**：N/A
- **原文链接**：http://arxiv.org/abs/2609.38248v1
- **PDF 链接**：https://arxiv.org/pdf/2609.38248v1
- **匹配主题**：os-kernel
- **相关性分数**：10
