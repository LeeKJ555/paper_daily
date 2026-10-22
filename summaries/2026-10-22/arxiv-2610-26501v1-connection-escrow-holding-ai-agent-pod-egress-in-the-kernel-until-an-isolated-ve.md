## 论文针对什么问题

AI agent 在容器中运行，通过打开网络连接来执行动作，而驱动它的文本可能带有敌意。现有控制大多位于应用层，例如网关检查工具调用、SDK 钩子否决调用、沙箱设置代理环境变量。这些手段可被以下方式绕过：

- 工具自己打开 socket，绕过网关或代理；
- 子进程直接建立连接，继承或绕过父进程限制；
- 运行时忽略代理设置。

即使未被绕过，应用层批准也没有绑定到内核随后实际打开的连接上，存在“批准是批准，连接是连接”的脱节。内核级策略如静态 allow-list 虽然能关闭应用层绕过路径，但通常只提供粗粒度、长期生效的允许规则：一旦目标地址被允许，它对范围内所有进程、所有连接持续有效。这类策略不能把某一次批准绑定到某一个特定 socket。

因此，论文要解决的核心问题是：在 agent 决定建立连接之后，如何在一个 agent 无法影响或绕过的位置检查该决策，并让检查结果与内核中实际发生的连接严格绑定。

## 提出了什么解决方案

论文提出 **connection escrow（连接托管）**：

- 每个出站 TCP 连接在 pod 的 cgroup 上由 98 条指令的 eBPF 程序在内核 `connect()` 路径中“停放”，此时尚未产生任何数据包。
- 节点上的 interceptor 对持有的 socket 做身份归属，包括内核 socket cookie、进程、可执行文件摘要、cgroup 和 pod 身份；同时停放 agent 写入的首批字节，例如 HTTP 请求行或 TLS ClientHello。
- 然后向运行在独立容器中的 verifier 发起检查请求，verifier 拥有自己的密钥，不受 agent 控制。
- 连接只有在收到签名 verdict 后才释放。verdict 必须满足：命名该 socket cookie 和目的地址、未过期、未被使用过。如果在截止时间内没有 verdict，连接被重置；迟到的批准会被拒绝。
- agent 本身无需修改。

方案同时支持在不终止 TLS 的情况下对请求内容进行门控：通过 eBPF uprobe 在 agent 的 TLS 库边界读取明文，由模型评分，并根据评分结果决定连接是否继续。这样 TLS 仍然保持端到端，enforcer 不持有任何密钥。

论文明确表示，具体的策略判定逻辑是可插拔且超出本文范围的；本文关注的是检查在哪里执行，以及如何把判定结果绑定到实际连接。

## 具体是怎么做的

### 设计选择：为什么使用 `connect()` hook

论文比较了若干可选执行点：

- **Sidecar / egress proxy**：例如 Envoy `ext_authz`、CONNECT 代理。它们只能看到工作负载主动发来的流量，无法阻止子进程或 raw socket 绕过；等代理看到请求时连接已经建立。
- **Netfilter queue / NFQUEUE**：可以持有数据包等待用户态判定，但作用于 socket 创建之后的首个数据包，归属信息需要事后扫描进程，存在竞态，并且没有工作负载身份概念，无法用于绑定到 pod 身份。
- **LSM hook / BPF-LSM**：同步且位于数据包之前，但判定只能是本地 allow/deny，不能睡眠等待外部 verifier，因此不适合承载需要远程判定并持有连接的场景。
- **traffic control 等其他位置**：摘要未提供足够细节，但正文指出 `connect()` hook 是唯一能满足“同步、预包、可睡眠等待外部验证者、且具备 cgroup 身份”要求的点。

因此，论文选择在内核 `connect()` 路径中停放连接，所有后续归属、verifier 调用和释放都挂载在该路径产生的 socket 上。

### 系统组件与工作流

监督工作负载是一个 Kubernetes pod，或更一般地是一个 control group，其中运行 agent 及其启动的工具进程。pod 拥有 service account，并据此获得平台身份，例如 SPIFFE SVID。verifier 是操作者信任的组件，运行在集群其他位置的独立 pod 中，拥有自己的密钥。

一次连接的处理流程如下：

1. pod cgroup 上的 eBPF 程序在 `connect()` 路径中停放出站 TCP 连接。
2. interceptor 对 socket 进行身份归属（socket cookie、进程、可执行文件摘要、cgroup、pod 身份）。
3. interceptor 停放 agent 写入的首批字节（HTTP 请求行或 TLS ClientHello）。
4. interceptor 向 verifier 发起请求，携带归属记录和捕获的字节。
5. verifier 根据可插拔策略做出判定，并返回签名 verdict。
6. 连接只有在收到满足条件的签名 verdict 后才释放：verdict 必须命名该 socket cookie 和目的地址、未过期且未使用。
7. 如果超时未收到判决，连接被重置；迟到的批准被拒绝。

### 实现要点

- 系统实现为 **Python + eBPF**，并提供 iptables 回退方案。
- eBPF 持有点挂载在 pod 的 cgroup 上，程序长度为 98 条指令。
- 内容门控扩展使用 eBPF uprobe，在 TLS 库边界读取明文。涵盖三种运行时形态：共享 OpenSSL、静态链接 OpenSSL（BoringSSL 形态）和 Go 的 `crypto/tls`。
- 论文附带一个规则引擎 verifier，支持按 SNI、主机或地址、端口、HTTP 方法和路径前缀进行判定，以及 per-workload budgets 和 operator hold。内容门控附带占位分类器。
- 评测包括 36 项对抗性检查、Kubernetes 集群实验和延迟拆解。

## 取得了什么效果

### 对抗性测试

在 Linux 6.18 和真实 cgroups 上，36 项对抗性检查全部通过 eBPF 持有点；其中 33 项也适用于 iptables 持有点并通过。关键结果包括：

- 被拒绝的连接从未到达目的地址；
- 伪造、重绑定、重放、过期和迟到的 verdict 均被拒绝；
- agent 试图访问 verifier 本身的连接也会被 escrow 拦截；
- 子进程绕过和重命名二进制绕过失败；
- UDP 被固定到 resolver，避免通过 UDP 绕过 TCP 控制。

### Kubernetes 集群实验

- 未修改的 pods 按连接被持有，并归属到其 SPIFFE 身份；
- 绕过 sidecar proxy 的 raw socket 也被 escrow 持有；
- 六个 pods 共打开 600 个连接，全部被门控。

### 延迟开销

在 loopback 场景下，每个释放连接增加约 4.3 ms 中位数（6.8 ms p95）。其中策略评估仅占 24 μs，其余时间用于属性归属、一次 HTTP 往返和两次签名。摘要中记录的中位数为 4.5 ms，正文摘录为 4.3 ms，存在轻微差异。

### 内容门控

在不终止 TLS 的前提下，eBPF uprobe 成功在三种 TLS 库形态（共享 OpenSSL、静态 OpenSSL/BoringSSL、Go `crypto/tls`）中读取明文并进行评分。针对 keep-alive 利用场景：同一连接上第一个良性请求被允许，后续恶意请求被识别并拒绝，服务器最终只收到第一个请求。

## 旁观者视角的问题与不足

- **延迟结构不利于高并发/低延迟场景**：每个连接增加 4.3 ms 中位数、6.8 ms p95，主要来自一次 HTTP 往返和两次签名。论文评估仅在 loopback 环境完成，未测量 verifier 跨节点部署时的网络往返延迟。对于大规模微服务或高 QPS 场景，这一开销可能显著。

- **fail-closed 模型存在可用性风险**：连接超时未收到 verdict 时会被重置，也就是说 verifier 不可用或网络抖动会导致所有受控连接失败。论文未报告 verifier 故障、密钥轮换或网络分区下的可用性影响，也未讨论降级策略或缓存机制。

- **内容门控依赖具体 TLS 库和 ABI**：演示覆盖共享 OpenSSL、静态 OpenSSL/BoringSSL 和 Go `crypto/tls`，但未覆盖其他常见实现（如 Java、Rust 的 TLS 栈，或自定义加密库）。通过 uprobe 读取用户态明文依赖库内部符号和结构布局，可能对版本高度敏感，论文未讨论长期维护成本和兼容性风险。

- **UDP 控制范围有限**：UDP 被固定到 resolver，论文没有给出通用 UDP 出站控制机制。若 agent 使用非 DNS 的 UDP 通道，是否能被有效约束尚不明确。

- **安全假设未充分展开**：系统假设 agent 无法逃逸容器或修改内核/eBPF。对于特权容器、root 用户或能够加载/卸载 eBPF 程序的攻击者，持有点本身可能被移除或篡改。论文未讨论这些前提。

- **验证者自身规模和密钥管理未评估**：签名 verdict 需要密钥，但论文未讨论多验证者、密钥轮换、签名撤销或验证者性能瓶颈。单验证者可能成为单点故障。

- **摘要与正文延迟数字不一致**：摘要写 4.5 ms 中位数，正文摘录写 4.3 ms（p95 6.8 ms）。虽不影响整体结论，但表明版本间存在细微出入，读者应当以正文为准并核对代码。

## 值得继续追踪的点

- **降低每连接延迟**：当前开销主要来自 HTTP 往返和两次签名。可研究本地缓存 verdict、批量验证、异步预取或短期短期凭证，以减少关键路径上的 RTT。
- **内容门控的泛化**：扩展更多 TLS 实现和运行时（Java、Rust、Chromium 网络栈等），并探索非 TLS 协议（如 gRPC、HTTP/3/QUIC、原始 TCP）的通用明文捕获与绑定机制。
- **验证者高可用与密钥管理**：设计多验证者共识、密钥轮换、短期 verdict 和撤销机制，避免单点故障和重放攻击，并评估跨节点部署的延迟和吞吐。
- **与现有网络策略/服务网格的组合语义**：论文提到该系统可与 NetworkPolicy 和服务网格组合，但具体如何避免重复策略、冲突或身份传递缺失，值得进一步研究。
- **更完整的安全属性论证**：从 `connect()` 到 release 的整个生命周期中，是否存在其他 TOCTOU 或绕过路径，可以通过形式化建模或更全面的威胁模型来验证。
- **UDP 和原始 IP 协议的扩展**：当前 UDP 仅被限制到 resolver，对非 TCP 流出通道的控制仍然有限。未来可以探索对 UDP、SCTP、原始 socket 的 per-connection escrow。
- **生产规模的部署评估**：在大型集群中测量 verifier 吞吐量、跨节点延迟、连接建立并发度，以及 eBPF 持有点对宿主内核性能的影响。

## 元数据与链接

- **标题**：Connection Escrow: Holding AI-Agent Pod Egress in the Kernel Until an Isolated Verifier Rules
- **作者**：Ashok Subbabhatta Gopalakrishna
- **来源**：arxiv
- **Venue**：arXiv cs.CR, cs.NI, cs.OS
- **DOI**：N/A
- **原文链接**：[http://arxiv.org/abs/2610.26501v1](http://arxiv.org/abs/2610.26501v1)
- **PDF 链接**：[https://arxiv.org/pdf/2610.26501v1](https://arxiv.org/pdf/2610.26501v1)
- **匹配主题**：os-kernel
- **相关性分数**：10
