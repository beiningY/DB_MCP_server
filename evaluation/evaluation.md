## Q1:如何查询 IVR 的成本？需要用到哪些表？


## R1：
根据提供的知识库，查询 IVR（交互式语音应答）成本主要分为**时长计费**（Operational/Detailed）和**按次计费**（Financial/PNL）两种逻辑，具体取决于供应商（Vendor）和业务场景（Marketing 营销或 Collection 催收）。

以下是具体的查询逻辑和涉及的表：

### 1. 基于时长计费 (Duration-based)

这是最常见的 IVR 成本计算方式，主要用于运营监控和供应商对账。核心公式为：**通话时长 (秒) × 单价因子**。

#### **Infinity 供应商**
*   **涉及表：**
    *   **营销 (Marketing):** `singa_bi.send_infinity_ivr_logs` (别名 `siil`) [2][4][9]
    *   **催收 (Collection):** `singa_bi.collection_v2-infinity_ivr_reports` (别名 `iir`) [2][5][16]
*   **计算逻辑：**
    *   **Sum(Duration/Billsec) × 6.993**：这是在多数 IVR 日志查询中使用的精确倍率 [4][7][8][9]。
    *   **Sum(Duration/Billsec) × 7**：在某些成本监控报表中使用该简化倍率 [2][5][13]。

#### **NX 供应商**
*   **涉及表：**
    *   **营销 (Marketing):** `singa_bi.send_ivr_logs` (别名 `sil`) [4][9][15]
    *   **催收 (Collection):** `singa_bi.collection_v2-nx_ivr_calls` [13]
*   **计算逻辑：**
    *   **Sum(Second) × 7.23**：用于发送 IVR 日志的成本计算 [4][7][9]。
    *   **Sum(Duration) × 7.5**：在 NG 通讯成本监控报表中使用该倍率 [13]。

#### **SME 供应商**
*   **涉及表：**
    *   `singa_bi.response_sme_ivr` (别名 `rs`) [12]
    *   `singa_bi.send_sme_ivr_logs` [12]
*   **计算逻辑：**
    *   **Sum(Duration) × 13**：SME IVR 的时长单价通常设定为 13 [13]。

---

### 2. 基于按次计费 (Volume-based)

在部分财务 PNL（损益表）报表中，IVR 成本是根据调用次数进行估算的。

*   **催收通讯成本 (Collection IVR Cost):**
    *   **涉及表：** `singa_bi.audio_sms_log` [1][11]
    *   **计算逻辑：** `COUNT(DISTINCT id) * 200` (即每次调用 200 印尼盾) [1]。
*   **营销通讯成本 (Marketing NX IVR Cost):**
    *   **涉及表：** `singa_bi.send_ivr_logs` [1][11]
    *   **计算逻辑：** `COUNT(DISTINCT id) * 225` (即成功调用每次 225 印尼盾) [1][11]。

---

### 3. 总结：核心涉及的数据库表

如果您需要编写查询语句，以下是核心表清单：

| 业务/供应商 | 核心表名 | 常用别名 | 关键字段 |
| :--- | :--- | :--- | :--- |
| **Infinity (营销)** | `singa_bi.send_infinity_ivr_logs` | `siil` | `duration` |
| **Infinity (催收)** | `singa_bi.collection_v2-infinity_ivr_reports` | `iir` | `billsec` |
| **NX (营销)** | `singa_bi.send_ivr_logs` | `sil` | `second` |
| **NX (催收)** | `singa_bi.collection_v2-nx_ivr_calls` | `nic` | `duration_seconds` |
| **SME** | `singa_bi.response_sme_ivr` | `rs` | `call_duration` |
| **通用/财务** | `singa_bi.audio_sms_log` | N/A | `id` (用于计数) |

### References

- [1] Query669:PNL NEW
- [2] Query1690:Cost - Infinity Coll and Marketing
- [9] Query2104:IVR
- [13] Query1553:NG Communication cost monitor
- [16] Query2092:Grand Total (Exc. WABA (Core))

## Q2:SMS 发送成本如何计算？不同供应商的单价是多少？

## R2：
根据提供的上下文，SMS 发送成本的计算逻辑主要基于发送的总量乘以特定供应商和通道的单价。以下是详细的计算方式和不同供应商的单价细分：

### 1. SMS 成本计算公式

SMS 成本通常通过以下公式计算：

$$ \text{总成本} = \text{SMS 发送总量 (Total SMS)} \times \text{单价 (Unit Price)} $$

*   **发送总量**：通常统计 `task_id` 或 `id` 的数量。
*   **单价**：取决于供应商（Supplier/Provider）和发送通道（Channel/Scenario，如 Marketing, Notice, OTP 等）。
*   **货币单位**：根据上下文中的数值（如 480, 88 等）和字段描述，通常为印尼盾 (IDR) [1][15]。

### 2. 不同供应商与通道的单价 (IDR)

根据不同的业务场景（催收、营销、APP通知），供应商的单价有所不同。以下是主要供应商的费率：

#### **Infinity (Supplier: INFINITY / InfinityNoticeSms)**
Infinity 的价格主要分为营销类和通知/验证码类：
*   **营销 (Marketing):** 单价通常为 **98** [1][4]。
    *   *注：在某些特定的 Collection 场景下，营销类 (mkt) 可能标注为 88 [19]。*
*   **通知与验证码 (Notice / OTP):**
    *   标准费率为 **480**（适用于 Channel 'notice' 和 'opt'）[1][4]。
    *   在某些特定成本监控报表中，Otp 可能为 **446**，Notice 为 **432**，OptSms 为 **495** [4][19]。

#### **NX (Supplier: NXTELE / NxInformSms / NxCodeSms)**
NX 的价格结构较为复杂，区分了通知、验证码和营销：
*   **营销 (Marketing):** 单价通常为 **120**（适用于 NxMarketingSms 或特定 Marketing 通道）[1][4][19]。
    *   *注：也有记录显示为 102 [1]。*
*   **验证码 (Code / OTP):** 单价精确为 **483.59** [1][19]，在部分聚合报表中取整为 **484** [4]。
*   **通知 (Inform / Notice):** 单价通常为 **120** [1][19]，部分报表中 NxInformSms 显示为 **484** [4]。

#### **NextOTP (Supplier: NEXTOPT)**
NextOTP 主要用于通知和验证码服务，价格较高：
*   **标准费率:** 通常为 **534**（适用于 'notice' 和 'opt'）[1]。
*   **变动费率:** 在不同的成本监控报表中，价格可能显示为 **497** [4] 或 **590** [19]。

#### **其他及通用费率**
*   **一般性估算:** 在某些通用统计（如不区分详细通道的报表）中，可能会使用统一的预估单价，例如 **88** [15][16] 或 **560** [10]。
*   **Alicloud SMS:** 在较新的成本监控中提到单价为 **0.0088** (可能是美元或其他结算单位，与上述 IDR 计价量级不同) [8]。

### 3. 不同场景下的价格汇总表

| 供应商 (Provider) | 通道/类型 (Channel) | 单价 (Price) | 备注 |
| :--- | :--- | :--- | :--- |
| **Infinity** | Marketing | 98 | 营销短信 |
| **Infinity** | Notice / OPT | 480 | 通知与验证码 (部分报表波动至 432-495) |
| **NX** | Marketing | 120 | 营销短信 (偶见 102) |
| **NX** | Code / OPT | 483.59 | 验证码 (部分报表取整 484) |
| **NX** | Inform / Notice | 120 | 通知短信 (部分报表显示 484) |
| **NextOTP** | Notice / OPT | 534 | 主要用于 APP 通知与验证码 (波动范围 497-590) |

### References

- [1] Query1973:SMS Cost
- [4] Query319:Message cost monitor
- [10] Query1953:SMS cost prototype
- [15] Query2108:SMS
- [19] Query2096:COST SMS

## Q3:WhatsApp 消息的费用是如何计算的？NX 和 Infinity 供应商的单价分别是多少？

## R3：
根据提供的上下文信息，WhatsApp 消息费用的计算逻辑及各供应商的单价如下：

### 计算逻辑

WhatsApp 消息的费用是基于**消息发送尝试的总次数（Total Attempt）**乘以特定供应商的**单价（Unit Price）**来计算的。系统首先会根据 `provider`（供应商）字段将数据归类为不同的供应商（Vendor），例如将 `NxWaTplMarketing` 归类为 "NX"，将 `Infinity` 归类为 "Infinity"，然后应用相应的费率进行求和或乘法运算 [5][7][15]。

具体的计算公式体现为：
*   **总费用 (Price in IDR) = 总尝试次数 (Total Attempt) × 供应商单价** [1][16][17]

### 供应商单价

根据主要的成本计算查询逻辑，不同供应商的单价（印尼盾 IDR）设定如下：

*   **NX**: 单价为 **663 IDR**。
    *   该价格通常适用于 `provider` 字段为 `NxWaTplMarketing` 的记录 [1][15]。
*   **Infinity**: 单价为 **666 IDR**。
    *   该价格适用于 `provider` 字段为 `Infinity` 的记录 [1][5][16]。

### References

* [1] Query2127:Grand Total (Exc. WABA (Core))
* [5] Query2111:WA
* [7] Query2110:WA
* [15] Query2124:COST WA
* [16] Query2134:COST WA

## Q4:GPT 外呼的成本记录在哪个表？单次调用费用是多少？

## R4：
根据提供的上下文信息，关于 GPT 外呼的成本记录表及单次费用如下：

### 1. 营销与通用 GPT 外呼 (Marketing/General)

在营销和通用任务的成本报告中，GPT 外呼的详细记录存储在 `send_gpt_logs` 表中。

*   **记录表名**：`send_gpt_logs` (别名 `sgl`)
*   **单次费用**：**600** (IDR/印尼盾)
*   **计算逻辑**：查询逻辑中直接使用 `COUNT(*) * 600` 来计算总费用。

### 2. 催收 GPT 批次 (Collection Schedule Batches)

在催收业务（Collection）的场景下，存在针对 GPT 渠道（Channel ID = 9）的批次记录表。

*   **记录表名**：`singa_bi.collection_v2-schedule_batches`
*   **单次费用**：**370** (IDR/印尼盾)
*   **计算逻辑**：针对 `channel_id = 9` 的记录，费用计算为 `COUNT(1) * 370`。

### 总结

通常情况下的 GPT 外呼日志主要参考 **`send_gpt_logs`** 表，单次调用费用为 **600 IDR**。如果是指催收业务中的 GPT 调度批次，则参考 `singa_bi.collection_v2-schedule_batches` 表，单价为 370 IDR。

### References

* [4] Query2130:Grand Total (Exc. WABA (Core))
* [5] Query2127:Grand Total (Exc. WABA (Core))
* [6] Query2092:Grand Total (Exc. WABA (Core))
* [7] Query2129:COST Grand Total (Exc. WABA (Core))
* [9] Query2119:COST Grand Total (Exc. WABA (Core))

## Q5:如何统计注册用户到填写银行信息的转化率？T0、T7、B1、B2 分别代表什么？

## R5：
根据提供的上下文，以下是关于如何统计注册用户到填写银行信息的转化率，以及 T0、B1、B2 等指标定义的回答：

### 1. 注册用户到填写银行信息的转化率统计

在提供的知识库中，针对必选认证流程（包含银行卡信息填写），转化率通常是基于**漏斗模型**逐步计算的。根据文档记录，具体的统计逻辑如下：

*   **计算逻辑**：
    虽然没有直接名为“注册->银行卡”的单一转化率指标，但通常通过分步转化率来衡量。填写银行卡信息的转化率通常是作为“联系人认证”后的下一步进行计算的。
    *   **公式**：`银行卡认证人数` / `联系人认证人数`
    *   **SQL 逻辑参考**：`round(sum(auth_bank_cust_cnt) / sum(auth_contact_cust_cnt) * 100, 2)`
    *   如果需要统计从**注册**直接到**填写银行信息**的整体转化情况，可以使用 `auth_bank_cust_cnt`（银行卡认证人数）除以 `regist_cust_cnt`（注册人数）。

*   **数据来源表**：
    *   主要来源于表 `BI_T1_003_customer_auth_flow_process_daily_v3`。
    *   该表记录了从注册（`regist_cust_cnt`）到各个认证环节（如身份、基础、工作、联系人、银行卡）的漏斗数据。

*   **相关漏斗步骤**：
    根据文档描述，必选认证的完整链路通常为：
    注册 -> 认证申请 -> 身份认证 -> 基础认证 -> 工作认证 -> 联系人认证 -> **银行卡认证 (`auth_bank_cust_cnt`)** -> 认证完成 [4][15]。

### 2. T0、T7、B1、B2 的含义

这些术语通常用于描述用户从**注册**到**首次申请**（或特定行为）的时间间隔（Time Interval / Bucket）。根据文档 `Query1855:注册到申请的B1,B2%` 中的定义：

*   **T0 (Same Day)**
    *   **含义**：用户在注册**当天**就进行了申请。
    *   **定义逻辑**：`diff_days = 0`。即申请日期与注册日期相同 [5]。

*   **B1 (Bucket 1)**
    *   **含义**：用户在注册后的 **1 到 14 天内**进行了申请。
    *   **定义逻辑**：`diff_days BETWEEN 1 AND 14` [5]。
    *   *补充*：文档中还提到了 `regist_b1`，指注册日期距离统计日期 1-14 天且尚未申请（或申请在统计日之后）的用户存量 [5]。

*   **B2 (Bucket 2)**
    *   **含义**：用户在注册后的 **15 到 28 天内**进行了申请。
    *   **定义逻辑**：`diff_days BETWEEN 15 AND 28` [5]。

*   **关于 T7**
    *   **缺失信息**：在提供的文档上下文中，**没有找到明确定义 "T7" 的具体描述**。
    *   *参考信息*：文档中存在 "T10 放款申请" 和 "T11 放款成功" 的步骤定义 [14]，但这指的是业务流程步骤代码（T series step），而非时间窗口。如果有 "T7" 的用法，依据行业惯例可能是指“注册后7天内”或“第7天”，但在当前提供的知识库中无法确证。

### References

* [4] Query630:Singa T1 003 用户必选认证转化
* [5] Query1855:注册到申请的B1,B2%
* [14] Query312:尼日自动化漏斗1
* [15] Query728:Singa T1 003 用户必选认证转化 (20230407之前)

## Q6:从产品额度确认到借款申请的转化流程是怎样的？涉及哪些表？

## R6：
根据提供的上下文信息，从产品额度确认（通常指授信通过或确认额度意向）到借款申请的转化流程主要涉及用户在获得授信后提交申请的各个阶段，主要包括“复借授信（S3）”到“申请（S4）”的流转，以及具体的点击确认行为。

以下是详细的转化流程及涉及的核心数据表：

### 1. 转化流程

从额度确认到申请的转化通常被划分为以下关键业务阶段（以复借流程为例）：

*   **S3 复借授信 / 授信通过 (Credit Granted):**
    *   这是流程的起点。系统通过风控审核（`audit_status = 'PASS'`），用户获得授信资格。
    *   相关事件：`re_credit_pass`（复借授信通过）。
*   **S6-1 确认额度 (Confirm Credit):**
    *   用户在前端页面看到额度后，进行点击确认的操作。
    *   相关事件：**`loan_apply_click`**。该事件标志着用户有申请意向，即“确认额度”阶段。
*   **S4 申请提交 (Application Submitted):**
    *   用户正式提交借款记录，系统记录申请提交时间 (`loan_apply_submit_time`)。
    *   相关指标：**`loan_apply_cust_cnt`**（借款申请人数）或 **`Reloan submitted`**（复借提交）。

在漏斗分析中，通常关注从 **S3 复借授信** 到 **S4 申请** 的转化率，这代表了获得额度的用户中有多少人最终发起了申请。

### 2. 涉及的数据表

该流程的数据主要存储在以下核心表中，用于记录审核状态、申请时间和订单详情：

*   **`loan_apply_main` (借款申请主表)**
    *   **作用**：这是管理借款申请生命周期的核心表。它记录了从申请提交到最终放款或拒绝的全过程。
    *   **关键字段**：
        *   `loan_apply_submit_time`：用于判定 S4 申请阶段的时间点。
        *   `split_order_id` / `order_id`：订单唯一标识。
        *   `credit_from_type`：额度类型（如 low, default, settle, another），用于区分不同的产品额度来源。
        *   `platform_reborrow_status`：区分平台首借或复借。

*   **`risk_audit_main` (风控审核主表)**
    *   **作用**：主要用于追踪授信阶段（S3）的状态。
    *   **关键字段**：
        *   `audit_status`：状态为 `'PASS'` 时表示授信通过（re_credit_pass）。
        *   `start_time`：记录授信审核开始或通过的时间。
        *   `reborrow_status`：用于筛选复借用户的授信记录。

*   **`singa_bi.approval_info` (审批信息表)**
    *   **作用**：作为审批流程的中央存储库，它包含了详细的订单审批记录和风控状态。
    *   **关联逻辑**：通过 `order_id` 与其他表关联，用于计算具体的通过率（如 Loan RC passed）和提取申请时的产品信息（`apply_product`）。

### 3. 数据逻辑示例

在计算从“复借授信”到“申请”的转化时，通常使用以下逻辑（基于 `CTE` 和 `UNION` 操作）：

1.  **提取授信记录**：从 `risk_audit_main` 中筛选 `audit_status = 'PASS'` 的记录，标记为事件 `S3`。
2.  **提取申请记录**：从 `loan_apply_main` 中筛选在指定时间窗口内提交申请的记录，标记为事件 `S4`。
3.  **关联分析**：通过 `user_id` 和时间顺序将 S3 和 S4 的记录串联，计算用户从获得授信到提交申请的留存或流失情况。

### References

* [3] Query834:Singa Loan T 119 用户(到期&结清)复借转化
* [5] Query987:复借风控审核
* [17] Query1206:Singa T 放款件数分布(额度类型)(全局lender有效)
* [6] Query989:New Query

## Q7:用户从联系人填写到借款申请的转化率怎么计算？

## R7：
根据提供的文档上下文，从“联系人填写”（通常包含在必选认证环节中）到“借款申请”的转化率，在系统中具体对应为**“认证完成->借款申请转化率”**。

具体的计算逻辑如下：

### 1. 计算公式
转化率的计算是用**借款申请人数**除以**认证完成人数**，结果以百分比表示。

*   **业务逻辑**：`认证完成->借款申请转化率` = `借款申请` / `认证完成`
*   **SQL 计算公式**：
    ```sql
    CONCAT(ROUND(SUM(loan_apply_cust_cnt) / SUM(auth_tot_finish_cust_cnt) * 100, 2), '%')
    ```

### 2. 字段定义
根据文档中的指标说明：
*   **分子（借款申请人数）**：`loan_apply_cust_cnt`，代表在统计周期内提交了借款申请的用户数量。
*   **分母（认证完成人数）**：`auth_tot_finish_cust_cnt`，代表完成必选认证（包括联系人填写等必要信息）的用户数量。即“认证完成项数=需要认证的项目数”的用户。

这一指标用于衡量完成了所有必要信息填写（如联系人认证）的用户中，有多少比例实际提交了借款申请。

### References
* [1] Query615:墨西哥 T1_001 用户流程转化
* [3] Query1195:Singa  Loan T1 001 用户流程转化

## Q8:借款人 APP 的核心漏斗有哪些步骤？从安装到放款成功的完整流程是什么？

## R8：
根据提供的上下文资料，借款人 APP 的核心漏斗通常被定义为 **S0 到 S9** 的一系列转化步骤。这个流程完整覆盖了用户从安装 APP 到最终放款成功的全生命周期。

以下是从安装到放款成功的完整核心流程拆解：

### 1.获客与激活阶段 (S0 - S1)
这一阶段主要追踪用户从下载安装到完成注册的行为路径。

*   **S0 安装 (S0 Install):** 用户完成 APP 的安装。
    *   在此阶段还有更细分的激活步骤，包括：
        *   **S0_1:** 首次打开 APP (First open app)
        *   **S0_2:** 输入手机号 (Input phone number)
        *   **S0_3:** 点击获取验证码 (Request SMS/OTP)
        *   **S0_4:** 验证码发送成功 (SMS sent success)
        *   **S0_5:** 设置密码 (Set password)
*   **S1 注册 (S1 Register):** 用户成功完成注册流程。

### 2. 认证与授信阶段 (S2 - S3)
用户注册后，需要进行身份验证和资料填写。

*   **S2 必选认证申请 (Auth Apply):** 用户开始填写必选认证信息（有必选认证记录）。
*   **S3 必选认证完成 (Auth Finish):** 用户完成了所有必选的认证步骤（必选认证完成步数等于总数），通常包括人脸识别、身份证上传及银行卡绑定等（部分新流程中可能细分为 S6 必选认证完成）。

### 3. 申请与审核阶段 (S4 - S7)
用户提交借款请求，系统及人工进行多轮审核。

*   **S4 借款申请 (Loan Application):** 用户正式提交借款申请。
*   **S5 风控审核通过 (Risk Audit Pass):** 申请通过了系统的风控模型审核。
*   **S6 信息审核通过 (Manual Audit Pass):** 申请通过了人工或系统的详细信息审核（在部分新定义中也可能涉及人脸比对 S6-2）。
*   **S7 终审审核通过 (Final Audit Pass/Blacklist Audit Pass):** 申请通过了最终审核（包括黑名单校验等）。

### 4. 放款阶段 (S8 - S9)
审核通过后，进入资金发放环节。

*   **S8 放款申请 (Issue Submit):** 系统向支付渠道提交放款请求。
*   **S9 放款成功 (Issue Success):** 资金成功发放给用户（Disbursement），这是漏斗的最终转化目标。

### 补充说明
针对**历史用户**（已注册过但在当日安装的用户）或**复借用户**，流程可能会简化，例如直接从“S1 登陆成功”进入“S2 可借款/有复借额度”，随后直接进入“S3 借款申请”及后续放款流程，跳过注册和基础认证环节。

### References

* [1] Query1303:Copy of (#276) Singa T 001 用户流程转化
* [2] Query1295:Singa T1 124 新用户首借流程转化(当日)
* [3] Query594:Singa T1 124 新用户首借流程转化(最新)
* [4] Query1563:NG install user core funnel trend_E
* [5] Query1598:NG install user core funnel_E

## Q9:漏斗数据中 loan_apply_click 事件代表什么业务含义？

## R9：
根据提供的上下文资料，`loan_apply_click` 事件在漏斗数据中代表以下业务含义：

### 1. 业务阶段映射
在漏斗分析的 SQL 逻辑中，`loan_apply_click` 通常通过 `CASE` 语句被映射为 **S6-1** 阶段。它具体的业务描述为 **“产品额度确认”** 或 **“必选认证完成-产品额度确认”** [2, 4, 6]。

### 2. 漏斗中的位置
该事件处于用户借款流程的中间环节，连接了认证步骤与最终申请步骤：
*   **前置步骤**：通常发生在“S6 必选认证完成”（对应 `image and bank` 事件）之后。
*   **后续步骤**：通常在“S6-2 人脸比对”（对应 `face` 事件）或“S7 借款申请”（对应 `apply_cust_cnt` 事件）之前 [12, 14]。

### 3. 具体行为描述
该事件标志着用户在完成必要的基础信息认证（如身份信息、银行信息）后，查看并确认系统给出的借款产品额度的行为，是用户进入最终人脸识别和提交借款申请前的关键转化点 [4, 14]。

### References

* [2] Query1707:NG_telesales tracking_E
* [4] Query2074:Borrower app core funnel trend_ng
* [6] Query1456:Borrower app core funnel trend
* [12] Query1813:（目前没有agency）NG_ FPD% by Agency_E
* [14] Query1513:NG Borrower app core funnel

## Q10:如何统计各渠道的获客成本（CPS、CPI、CPA）

## R10：
根据提供的上下文，统计各渠道的获客成本（CPS、CPI、CPA）主要依赖于 `singa_bi.deliver` 表中的数据，通过 SQL 查询对通过、申请、安装和成本等字段进行聚合计算。

以下是具体的统计方法和计算逻辑：

### 1. 核心计算公式

在数据仓库的计算逻辑中，由于基础数据表 `singa_bi.deliver`（在查询中通常被定义为 `base` CTE）包含了成本和各类转化漏斗的数据，各指标的计算公式如下：

*   **CPI (Cost Per Install)：** 单个安装成本。
    *   计算公式：`SUM(cost) / SUM(installed)`
    *   逻辑：总消耗金额除以总安装数 [2][3][14][16]。
*   **CPA (Cost Per Apply)：** 单个申请成本。
    *   计算公式：`SUM(cost) / SUM(applied)`
    *   逻辑：总消耗金额除以总申请数（部分查询中也称为 `loanapplied`）[2][3][14][16]。
*   **CPS (Cost Per Success/Pass)：** 单个通过成本（风控通过）。
    *   计算公式：`SUM(cost) / SUM(passed)` 或者 `SUM(daily_cost)/SUM(daily_pass)`
    *   逻辑：总消耗金额除以风控通过数。部分报表还会根据渠道不同设定“CPS要求”基准值（如 CyberAds-FB 为 20，Facebook 为 34 等）进行对比 [4][14][16]。

### 2. 渠道分类与定义逻辑

为了准确统计“各渠道”的成本，需要对原始数据中的 `channel`、`agency` 和 `media_source` 字段进行清洗和分组。数据处理通常包含以下逻辑：

*   **渠道类型划分 (Cata)：**
    *   **AGENCY (代理)：** 当 `agency` 自段不为空，且渠道不是自投（非 'Facebook', 'Google Ads' 等）时。
    *   **OWN (自投)：** 当渠道包含“自投”、或是 'Facebook'、'Google Ads' 等直投平台，或 `agency` 为空时。
    *   **ORGANIC (自然量)：** 当 `media_source` 为空或为 'organic' 时。
*   **具体渠道重命名与组合：**
    *   通过 `CASE WHEN` 语句将复杂的渠道名称标准化。例如，将 `googleadwords_int` 归类为 `GG`，将 `restricted` 或 `Facebook Ads` 归类为 `FB`，将 `Apple Search Ads` 归类为 `ASA` 等 [6][10]。
    *   在特定的营销报表中，还会根据平台（iOS/Android）和代理商前缀（如 'CyberAds'）组合生成 `grouped_channel`（例如：`android-CyberAds（北京思倍）-FB`）[4]。

### 3. 数据处理流程

统计通常遵循以下 SQL 处理步骤：
1.  **基础数据提取 (Pre-processing)：** 从 `singa_bi.deliver` 表中筛选特定日期范围（如 `attributed_date`）和平台（Platform），生成中间表（CTE `base`）。
2.  **聚合计算 (Aggregation)：** 按照处理后的渠道字段（如 `channel` 或 `grouped_channel`）进行 `GROUP BY` 分组。
3.  **指标运算：** 在分组的基础上，应用上述 CPI、CPA、CPS 的除法公式计算最终成本指标，并按成本或渠道进行排序输出 [2][16]。

### References

- [1] Query669:PNL NEW
- [2] Query1801:营销数据明细
- [3] Query1795:New Query
- [4] Query1808:7天营销数据
- [5] Query1116:墨西哥 T1 064 贷超API流量

## Q11:organic 和非 organic 渠道的获客数据存在哪个表？

## R11：
根据提供的上下文信息，Organic（自然流量）和非 Organic（非自然流量/付费流量）渠道的获客数据主要存在于以下表中：

### 1. 主要基础信息表：`pl_customer_basic_info`
这是存储客户注册信息、概况和元数据的核心源表（通常位于 `singa_redash` 数据库架构中）。它包含了识别用户获取来源的关键列 **`channel_name`**。
*   **区分逻辑**：在该表中，直接通过查询 `channel_name` 字段来区分渠道。通常将值为 `'organic'` 的记录定义为自然流量，而将 `channel_name != 'organic'` 的记录归类为非 Organic 渠道 [1][3][5][11]。
*   **应用场景**：该表被广泛用于生成包含“总计”、“organic”和“非organic”的渠道列表，用于后续的风险分析、Vintage 报表和获客质量分析 [2][7][13][17]。

### 2. 每日风控模型表：`temp_rc_model_daily`
位于 `singa_bi` 或 `singa_bi_ng` 架构下的 `temp_rc_model_daily` 表也是区分获客来源的重要数据源。
*   **关键字段**：该表使用 **`user_channel_source`** 字段来记录获客来源。
*   **区分逻辑**：与基础信息表类似，查询逻辑通常包括筛选项 `user_channel_source = 'organic'` 或排除项，以划分自然与非自然流量 [9][15]。

### 3. 客户流与注册报表表：`Loan_BI_124_customer_flow_regist_new_daily_v3`
这是一个主要用于日报流程的源表，包含客户流和注册指标。
*   **应用场景**：在分析 S0 到 S9 的转化漏斗时，该表被用来根据注册渠道（`regist_channel`）过滤数据。逻辑上明确将 `非organic` 定义为 `channel_name <> 'organic'` [4]。

### References

* [1] Query1329:list_Singa 财务v2_注册渠道
* [2] Query1360:Power 财务 019 vintage&RAR&逾期滚动(简版)
* [3] Query672:list_Singa T_注册渠道
* [4] Query594:Singa T1 124 新用户首借流程转化(最新)
* [5] Query1370:list_Singa T1_注册渠道

## Q12:FPD（首逾率）是如何计算的？按哪些维度进行分析？

## R12：
根据提供的知识库数据和文档片段，FPD（First Payment Default，首逾率）是用于评估信贷风险和早期还款表现的关键指标。以下是关于其计算逻辑和分析维度的详细说明：

### 1. FPD（首逾率）的计算逻辑

FPD% 的核心定义是计算在**首次还款日（或指定到期日）截止时**，未能按时归还的金额占比。它通常通过计算“按时还款率”后用 1 减去该值来得出，或者直接计算未还金额的占比。

**核心公式：**
$$FPD\% = \left( 1 - \frac{\text{到期日及之前实际归还的本息总额}}{\text{到期应还本息总额}} \right) \times 100\%$$

**具体计算规则与条件：**
*   **时间判定**：系统会将实际还款时间戳（`repay_at` 或 `repay_at_1`）与到期日（`expire_at`、`expire_at_1` 或 `term_end_date`）进行精确比较。只有当还款发生在到期日之前或当天（`repay_at <= expire_at`），才被视为正常还款 [1, 6, 20]。
*   **订单状态（Order Status）判定**：
    *   **状态 90**：通常代表全额结清。如果发生在到期日内，计入已还金额 [6, 20]。
    *   **状态 40**：通常代表部分还款。如果发生在到期日内，计入已还金额 [6, 20]。
    *   **状态 93**：通常代表订单已关闭或展期（Rollover）。在某些特定逻辑（如计算 Newloan_fpd 或 Reloan_fpd）中，展期可能被视为按时还款或特殊处理 [12, 20]。
*   **分母范围**：计算基数通常是所有截止到当前日期已经到期的订单的应还金额总和（`due_amount`） [6, 17]。

### 2. 分析维度

根据文档中的查询逻辑，FPD 指标通常按以下维度进行细分和分析：

*   **产品与贷款期数维度 (Product & Term)**
    *   **按期数**：详细区分第1期（Term 1）、第2期（Term 2）直至第4期的 FPD% [1]。
    *   **按产品ID**：将不同产品 ID 进行分组分析。例如，特定产品组（91, 95）、（92, 94）或特定新老客产品（23401, 23402）的表现 [6, 17, 20]。
    *   **新老客区分**：明确区分新客贷款（Newloan）和复贷（Reloan）的首逾率 [20]。

*   **时间维度 (Time Period)**
    *   **按日/周**：按放款日期（Loan Issue Time）或到期日（Expire Date）的日粒度或周粒度（Week Period）进行追踪 [1, 7, 10]。
    *   **按月对比**：分析当前月（Current Month）、上月（-1 Month）、上上月（-2 Month）的 FPD% 趋势，以观察长周期的风险变化 [8, 16]。

*   **渠道与平台维度 (Channel & Platform)**
    *   **注册渠道**：区分流量来源，如 Google、Facebook、Bytedance、Organic（自然流量）以及其他渠道，评估不同获客渠道的质量 [13]。
    *   **设备平台**：对比 Android 与 iOS 用户的首逾表现 [15]。

*   **用户与额度维度 (User & Amount)**
    *   **风险源 (Risk Source)**：区分不同的风控模型标签，如 Singa、UKU、Cloudun 等 [1, 14, 17]。
    *   **提额变动组 (Change Group)**：分析用户额度变动幅度对逾期的影响，例如额度变动在 [0, 0.5M)、[0.5M, 0.7M) 等不同区间的用户 FPD% [10]。

### References

* [1] Query685:分期贷后情况
* [6] Query1835:Old Customer-FPD% by due date
* [10] Query1138:Paidoff_Change_FPD_
* [13] Query611:新客贷后表现_渠道
* [20] Query1647:NG_FPD%_E

## Q13:DPD 和 NPL 率是通过哪些表计算的？

## R13：
根据提供的上下文信息，DPD（逾期天数，文档中常体现为 FPD、DPD7、unpaid_D1 等）和 NPL（不良贷款率）是通过多种不同的表组合计算的，具体取决于业务场景（如财务报表、催收监控或风控模型）。

以下是主要的计算来源表及其用途：

### 1. 核心还款计划与借款申请表 (用于财务与分期分析)
这类表通常用于计算具体期数（Term）的 FPD% 和 NPL%，特别是在涉及 `singa_redash` 的查询中。

*   **`singa_redash.pl_account_loan_repay_plan` (别名 t1)**：包含还款计划详情，如应还本息 (`term_principal_and_interest`)、实际还款总额 (`actual_repay_tot`)、期数 (`term_no`) 和结算时间。
*   **`singa_redash.loan_apply_main` (别名 t2)**：包含借款申请主信息，如 `split_order_id`、放款时间 (`loan_issue_time`)、贷款状态 (`loan_status`) 和产品 ID。
*   **计算逻辑**：通常通过连接这两张表，用 `1 - (实际还款 / 应还款)` 的公式来计算 FPD% 和 NPL% [3, 5, 7, 9, 13, 15]。

### 2. 催收订单与分期表 (用于 NPL Collection V2)
在催收（Collection）相关的报表中，使用专门的 V2 订单和分期表来计算 NPL% 和 NPL Target%。

*   **`singa_bi.collection_v2-installments` (别名 i)**：包含分期详情，如到期日 (`expire_at`)、应还金额 (`due_amount`) 和还款金额 (`repayment_amount`)。
*   **`singa_bi.collection_v2-orders` (别名 o)**：包含订单状态 (`order_status`)，用于判断订单是否已流入不良状态（如状态 93）[2, 4]。

### 3. 每日风控模型与订单表 (用于 DPD7, FPD, NPL 监控)
在 NG (Nigeria) 或特定的风控监控报表中，结合每日模型快照和原始订单表来计算不同阶段（如 DPD7、逾期未付 unpaid_D1/S1）的指标。

*   **`singa_bi_ng.temp_rc_model_daily` 或 `singa_bi.temp_rc_model_daily` (别名 t2)**：作为基础表，存储每日风控模型记录、申请时间、应还款日 (`expire_at_1`) 和风险源信息。
*   **`singa_bi_ng.sgo_orders` 或 `singa_bi.sgo_orders` (别名 t1)**：原始订单表，用于获取实时的订单状态（40, 90, 93）、实际还款时间和逾期天数 (`DATEDIFF`)。
*   **计算逻辑**：通过判断订单状态和当前日期与到期日的差值（如 `CURDATE() - INTERVAL 7 DAY`）来计算 DPD7% 和 FPD% [10, 14, 17, 19]。

### 4. 专用中间表与 CTE
*   **`first_term_data`**：这是一个专用的源表，直接用于计算特定产品（如 91, 95, 96, 101）的首期 FPD% 和 NPL%。它预处理了到期日 (`expire_at_1`) 和订单状态信息 [1]。
*   **Entity `B` (CTE)**：这是一个包含复杂逻辑的中间表/CTE，用于关联拒单原因 (`reasons_refusal`) 和风险来源 (`risk_source`)。它常作为辅助表连接到上述主表，用于筛选特定风险客群的 NPL 表现 [3, 5, 7]。
*   **`dtl` (CTE)**：被描述为一个核心的数据转换层，用于汇总逾期余额 (`overdue balances`) 和计算 NPL [Entity: dtl]。

### 5. 辅助筛选表
为了计算特定渠道或用户群体的 NPL/DPD，计算过程还会关联以下表：
*   **`singa_redash.pl_customer_basic_info` (别名 t4)**：用于获取渠道名称 (`channel_name`) 和平台信息 [7, 9]。
*   **`singa_bi.approval_info`**：用于获取机器审核状态 (`machine_status`)，以筛选通过风控的订单 [5, 15]。
*   **`singa_bi.sg_user_rejected`**：用于排除或分析被拒用户 [16, 19]。

### References

* [1] Query1834:New Customer-FPD% by due date
* [2] Query597:xiyue_NPL Collection V2_Total
* [3] Query989:New Query
* [4] Query1482:NPL Collection V2_Total_Dynamic (base)
* [5] Query1015:First_Change_FPD_

## Q14:催收渠道有哪些？各渠道的成本数据存在哪些表？

## R14：
根据提供的上下文信息，催收渠道主要可以分为具体执行催收任务的**机构/代理渠道**（执行方）和用于触达客户的**通讯渠道**（工具）。各渠道的成本数据分布在不同的源表和统计表中。

以下是详细的分类及对应的数据表来源：

### 1. 通讯渠道与成本数据表

通讯渠道指用于联系借款人的具体技术手段，包括短信、语音、WhatsApp 等。其成本数据主要存储在以下表中：

*   **Infinity Webcall（网页电话）**:
    *   **数据表**: `singa_bi.collection_v2_channel_report_infinity_phone_call`
    *   **成本逻辑**: 记录时长 (`billsec`)，通常以时长乘以单价（如 7 Rp）计算总成本 [5]。
*   **Infinity IVR（自动语音应答）**:
    *   **数据表**: `singa_bi.collection_v2-infinity_ivr_reports`
    *   **成本逻辑**: 同样基于时长 (`billsec`) 计算成本 [5]。
*   **SMS（短信）**:
    *   **数据表**: `dc_sms_cost`
    *   **指标与成本**: 统计字段为 `dc_sms调用次数`。在 PNL（损益）计算中，成本通常按次数乘以单价（如 450）计算 [3]。
*   **普通 IVR**:
    *   **数据表**: `dc_ivr_cost`
    *   **指标与成本**: 统计字段为 `dc_ivr调用次数`。成本通常按次数乘以单价（如 200）计算 [3]。
*   **WhatsApp (Utility / Utility)**:
    *   **指标**: `dc_wa_utility调用次数`
    *   **及其他通讯方式**: 包括 **NX** (`dc_nx调用次数`)、**AI** (`dc_ai调用次数`) 和 **Missed Call** (`misscall调用次数`)。这些通常在成本统计报表中通过特定的 JOIN 操作获取（如别名 `t16`, `t17`, `t18` 所对应的表，但在提供的片段中未显示完整表名，仅显示了字段引用）[3]。

### 2. 执行渠道（机构/团队）

执行渠道指负责具体催收业务的团队或委外公司。在数据中，主要通过 `outside` 字段进行区分，并通过 `tb_loan_collection` 表映射为具体的公司名称。

*   **内部团队 (Inhouse)**: 标识为 `Inhouse` 或 `Inhouse_2`。
*   **外部机构 (Vendor/Agency)**: 包括但不限于以下公司：
    *   SSS, LBT, Xinghao, PT EDN, Debito, MKM, FC
    *   Indocoll, Kalonay, Telmark, TIN, Colmitra
    *   Machine (机器催收), Special Case, Backup 等。
*   **数据来源**:
    *   公司名称映射表：`singa_bi.tb_loan_collection`（主要通过 `outside` 字段映射）[14], [16], [18]。
    *   在成本计算表中，虽然列出了 `催收内部人力成本` 和 `催收外部人力成本` 的字段，但在提供的 SQL 逻辑中这些字段目前显示为空值或者是占位符，具体的金额数值可能来源于其他系统或手动填报 [3]。

### 3. 综合成本计算逻辑

在 PNL（损益表）相关的查询中，**催收通讯成本**是汇总计算的。计算公式涵盖了上述所有通讯渠道的费用总和：
> `催收通讯成本 = SMS成本 + IVR成本 + WA Utility成本 + NX成本 + AI成本`

这些数据被汇总在名为 `main_result`、`due_result` 等结果集的关联查询中，特别是通过连接 `dc_sms_cost`、`dc_ivr_cost` 等分项成本表来生成最终报表 [3]。

### References

* [3] Query669:PNL NEW
* [5] Query1690:Cost - Infinity Coll and Marketing
* [14] Query1219:T0 Perform. Vendor Rank
* [16] Query1292:S2 Perform. Vendor Rank
* [18] Query986:T1,T2 Perform. Vendor Rank

## Q15:WABA Core 催收的费用是如何计算的？涉及哪些表？

## R15：
根据提供的上下文信息，WABA (WhatsApp Business API) 核心催收费用的计算主要涉及对不同来源表的数据聚合与筛选，具体逻辑如下：

### 计算逻辑

WABA 催收费用的计算通常根据数据的层级（聚合费用表或原始日志表）采用以下两种方式：

1.  **基于费用表的金额聚合**：
    *   直接基于 `waba_costs` 表进行统计，核心计算逻辑是针对 **Utility（工具/效用）** 类型的费用进行求和。
    *   具体公式为：`SUM(utility)`，即聚合 `utility` 列的数值作为效用金额（util_amount）。
    *   在特定分析（如催收重构分析）中，会进一步筛选出 `total > 0` 的记录，并结合还款阶段（如 T-1, S1 等）进行细分统计 [11]。

2.  **基于日志表的调用次数统计**：
    *   基于原始日志表 `singa_bi.is_send_sms_log` 计算调用量。
    *   筛选条件通常为：
        *   **平台 (platform)**：`'collection'`（催收）
        *   **场景 (scenario)**：`'SEND_NX_WA_TPL_UTILITY_MSG'`
        *   **供应商 (provider)**：`'NxWaTplUtility'`
        *   **状态 (is_success)**：`1`（发送成功）
    *   计算方式是统计去重后的 ID 数量：`COUNT(DISTINCT id)`，以此代表 WABA Utility 催收的调用次数 [1][4]。

### 涉及的表

计算过程主要涉及以下数据库表：

*   **`waba_costs`**：
    *   这是核心费用表，包含了 WABA 任务的详细成本分类（Utility, Marketing, Service, Authentication）。计算催收费用时主要使用其中的 `utility` 和 `TaskId` 字段 [11][17]。
*   **`singa_bi.is_send_sms_log`**：
    *   这是发送日志源表，用于从底层记录中筛选出属于催收平台（collection）且发送成功的 Utility 模版消息日志，用于计算调用次数或验证费用 [1][4]。
*   **`gpt_agent_order_info`**：
    *   该表常与 `waba_costs` 进行关联（通过 `TaskId`），用于引入业务维度信息（如 `repaymentstage`），以便按还款与逾期阶段（如 D1, T0, S1 等）分析催收费用 [11]。

### References

* [1] Query669:PNL NEW
* [4] Query748:PNL NEW MONTH
* [11] Query901:New recode for cost waba collection
* [17] Query648:waba-cost-telemarketing-day-detail

## Q16:按产品维度统计放款金额需要用到哪个表？

## R16：
根据提供的上下文信息，按产品维度（`product_id`）统计放款金额（`contract_amount` 或 `Disbursed$`）主要涉及到以下数据库表：

### 主要统计表

*   **`singa_bi.cyc_Loan_summary_app`**
    在“放款数据汇总”相关的查询中，该表被用于按 `product_id` 对客户性质进行分类（例如：91/95为新户，92为老户，93为首复借第1笔等），并计算 `sum(contract_amount)` 以得出“放款金额(印尼盾)” [5]。

*   **`singa_bi.temp_rc_model_daily`** (及 **`singa_bi_ng.temp_rc_model_daily`**)
    该表是风控模型日报的基础物理源表，用于按 `product_id`（如 23401, 23402, 92, 94 等）区分新客（Newloan）与老客（Reloan），并聚合计算放款金额（`SUM(contract_amount) AS 'Disbursed$'` 或 `disbursed avg$`）[9][12]。

### 基础源表

*   **`sgo_orders`**
    作为核心订单表，它包含原始的 `product_id` 和 `contract_amount` 字段。在需要详细订单流水的查询中，常通过该表关联其他信息来获取各产品的放款合约金额 [11]。

### References

* [5] Query443:fq放款数据汇总-昨日
* [9] Query2048:Loan overview T1_ng
* [11] Query1887:放款测试表
* [12] Query734:New Query

## Q17:如何查询每小时的放款申请量和通过量？

## R17：
根据提供的知识库和文档片段，目前的资料主要集中在**按日（Daily）**和**按月（Monthly）**维度的统计报表，没有直接提供针对“每小时”维度的预计算表或具体SQL查询语句。

不过，我们可以根据现有“日报表”的计算逻辑，解析出查询“放款申请量”和“通过量”所依赖的核心字段和数据定义。

### 1. 核心指标定义与计算逻辑

在现有的统计逻辑中，“放款申请量”和“通过量”是通过汇总**首借（First Borrow, FB）**和**复借（Repeat Borrow, RB）**的数据得出的：

*   **放款申请量 (Loan Application Volume)**
    *   **对应指标**：文档中称为“放款申请件数”。
    *   **计算公式**：`coalesce(sum(issue_submit_cnt_fb),0) + coalesce(sum(issue_submit_cnt_rb),0)`
    *   **说明**：这是“首借放款申请件数”与“复借放款申请件数”的总和 [1][2][3]。

*   **通过量 / 放款量 (Approval / Disbursed Volume)**
    *   **对应指标**：文档中称为“放款件数”或“放款成功件数”。
    *   **计算公式**：`coalesce(sum(issue_cnt_fb),0) + coalesce(sum(issue_cnt_rb),0)`
    *   **说明**：这是“首借放款件数”与“复借放款件数”的总和。有时也使用 `issue_success_cnt_fb` + `issue_success_cnt_rb` 来表示放款申请中的成功件数，用于计算放款成功率 [1][2][3]。

### 2. 数据来源表

现有的统计数据主要来源于以下日报表。如果需要进行更细粒度（如每小时）的查询，通常需要基于这些表对应的底层明细表（如 `singa_bi.approval_info` 或 `disbursements`，虽然文档未提供明细表的SQL示例）进行时间戳截取：

*   **主要来源表**：`BI_T1_000_overview_daily_v2_lender` 或 `BI_T1_000_overview_daily_v2`。
*   **其他相关表**：`BI_T1_001_customer_flow_process_daily_v2`（包含从放款申请到放款成功的转化漏斗数据，如 `issue_submit_cust_cnt` 和 `issue_success_cust_cnt`）[6][7]。

### 3. 查询建议

由于文档中仅包含 `GROUP BY calendar_date`（按日聚合）的示例，若您需要查询每小时数据，在拥有底层数据权限的情况下，逻辑应当是将上述计算字段的聚合维度从 `date_format(calendar_date, '%Y%m%d')` 更改为包含小时的时间维度。

**注意**：文档中未包含按小时 `GROUP BY` 的具体代码片段，以上逻辑基于日报表的字段定义推导 [1][3]。

### References

- [1] Query1372:Singa Loan T1 000 overview(lender有效)
- [2] Query1380:Singa Loan T1 000 overview(lender有效)
- [3] Query909:Singa Loan T1 000 overview
- [6] Query615:墨西哥 T1_001 用户流程转化
- [7] Query1513:NG Borrower app core funnel

## Q18:数据成本监控涉及哪些第三方服务？费用如何计算？

## R18：
根据提供的上下文，数据成本监控涉及多个领域的第三方服务商，其费用的计算通常基于**调用次数（Count）**或**时长（Duration）**乘以特定的**单价（Rate/Price）**。

以下是涉及的第三方服务及其具体的费用计算逻辑：

### 1. 第三方服务商分类

数据成本主要涵盖风控验证、通信服务、电子签约及银行查询等类别。主要涉及的供应商和服务包括：

*   **风控与身份验证类 (Risk & Verification):**
    *   **IZI:** 提供活体检测 (Liveness detection)、多头借贷检查 (Multiple)、OCR 识别、人脸比对 (Face comparison)、电话重连 (Phone reconnection) 等服务 [5][7][9]。
    *   **TD:** 提供活体检测、设备指纹 (Device fingerprint)、多头检查、邮箱验证 (Email) [5][7][9]。
    *   **Advance:** 提供多头信贷检查 (Advance multiple) [5]。
    *   **Filex:** 提供风险评分 (Risk score) [9][11]。
    *   **NX:** 提供 HLR (Home Location Register) 查询服务 [5]。
*   **通信与营销类 (Communication & Marketing):**
    *   **Infinity:** 提供 IVR（语音互动应答）和 WhatsApp (WABA) 服务 [17]。
    *   **NX (NextCode/NxInform):** 提供短信 (SMS)、语音通话 (Call) 和 WhatsApp 服务 [1][17]。
    *   **MontyMobile, NextOTP:** 提供短信服务 [1]。
    *   **OpenAI (GPT):** 涉及 GPT 调用服务 [17]。
*   **电子签约与账户类 (Signing & Banking):**
    *   **Privy:** 提供用户注册 (Regist) 和电子签名 (Sign) 服务 [7][13]。
    *   **银行渠道:** 包括 Permata 和 BCA 的账户查询服务 (Account inquiry) [5][7]。

### 2. 费用计算方法

大多数费用是通过 SQL 查询中的逻辑进行聚合计算的。具体的计算公式如下：

#### A. 风控与数据验证类费用
此类费用通常按**单次调用**计算，部分涉及汇率换算（如乘以 16000，推测为美元转印尼盾汇率）或固定费用分摊。

| 服务类别 (Cata) | 计算公式 / 单价 (Cost Calculation) | 来源参考 |
| :--- | :--- | :--- |
| **IZI Liveness detection** | `Count * 0.015 * 16000` | [5][7] |
| **IZI Multiple** | `Count * 0.008 * 16000` | [5][7] |
| **IZI OCR / Face comparison**| `Count * 0.002 * 16000` | [5][7] |
| **IZI Phone reconnection** | `Count * 0.1 * 16000` | [5][7] |
| **TD Liveness detection** | `Count * 0.006 * 16000` | [5][7] |
| **TD Device fingerprint** | `1500 / 30 * 16000` (按固定金额分摊) | [5][7] |
| **TD Email** | `Count * 117` | [5][7] |
| **Advance Multiple** | `Count * 630` | [5][7] |
| **NX HLR** | `Count * 22` | [5][7] |
| **Filex Score** | `Count * 1150` | [9][13] |
| **TKG** | `Count * 2 * 2200` | [5][7] |

#### B. 电子签约与银行查询费用
此类费用主要采用固定的单次价格。

| 服务类别 (Cata) | 单价 (Unit Price) | 来源参考 |
| :--- | :--- | :--- |
| **Privy Regist / Sign** | `1000` (每单) | [5][7] |
| **Permata / BCA Account Inquiry**| `100` (每单) | [5][7] |

#### C. 通信与营销类费用
此类费用计算较为复杂，分为按**时长**计费和按**条数**计费，且不同供应商价格不同。

*   **IVR / 语音通话 (按时长计费):**
    *   **Infinity IVR:** `总时长(Duration) * 6.993` [17]
    *   **NX IVR:** `总秒数(Second) * 7.23` [17]
    *   **NX Call:** `总时长(Duration) * 7.45` [17]

*   **短信与 WhatsApp (按条数计费):**
    *   **SMS (所有供应商):** `Count * 88` [17]
    *   **WhatsApp (NX):** `Count * 663` [17]
    *   **WhatsApp (Infinity):** `Count * 666` [17]
    *   **GPT:** `Count * 600` [17]

#### D. 综合指标
*   **平均成本 (Average Cost$):** 对于充值等交易，平均成本计算为 `SUM(vendor_fee) / 成功交易次数` [6]。
*   **每销售成本 (CPS):** `总费用(Cost) / 总单数(Cnt)`，以及累积 CPS (`cps_accu`) [19]。

### References

- [1] Query748:PNL NEW MONTH
- [5] Query1926:NG_Data cost monitor_copy
- [6] Query1954:VA - b2c
- [7] Query318:Data cost monitor
- [17] Query2130:Grand Total (Exc. WABA (Core))

## Q19:风控通过率（RC Pass Rate）如何按标签分组统计？

## R19：
根据提供的文档内容，风控通过率（RC Pass Rate/Loan RC passed%）的计算基础是：在提交的贷款申请（`type = 0`）中，机器审核状态为通过（`machine_status = 1`）的订单占比。

针对不同标签（Tag）的分组统计，系统主要通过 SQL 查询中的 `CASE` 语句，结合 **`risk_source`（风控来源）** 和 **`reasons_refusal`（拒绝原因代码）** 字段来进行逻辑划分。

具体的标签分组逻辑如下：

### 1. 不同标签（RC_tag）的定义逻辑

根据上下文中的查询逻辑（主要参考 `{{RC_tag}}` 参数的处理方式），各分组的判定规则如下：

*   **Total (整体):**
    *   不进行特定筛选（逻辑条件为 `1=1`），包含所有数据 [2][4][15]。

*   **UKU:**
    *   **主要条件**：`risk_source = 2`（或 `risk_source_0 = 2`）[2][8][18]。
    *   **补充条件**（当 `risk_source` 为空时）：根据拒绝原因代码判定。如果你被以下代码拒绝，则归类为 UKU 相关的流量：`reasons_refusal` 包含 `100, 13, 14, 1040, 1041, 1042, 1043, 1061, 1063, 1064, 1067, 1068, 1069, 1070, 1071, 1072, 1073, 1091, 1098, 1099` 等 [2][4][15]。

*   **Singa:**
    *   **主要条件**：通常定义为 `risk_source = 0` [4][8][18]。
    *   **变体情况**：在某些报表中，Singa 分组可能包含 `risk_source` 为 `0` 和 `5` 的数据 [2]。
    *   **排除逻辑**：在某些仅使用拒绝代码归类的逻辑中，Singa 被定义为**排除**掉 Cloudun（99）和 UKU（上述列表）特定拒绝代码之外的所有流量 [4][6][15]。

*   **Cloudun:**
    *   **主要条件**：`risk_source = 1`（或 `risk_source_0 = 1`）[2][8]。
    *   **补充条件**：`reasons_refusal = 99` [2][6][15]。

*   **Touchtown:**
    *   定义为 `risk_source_0 = 5` [18]。
    *   *注：在部分报表中，`risk_source = 5` 可能被归入 Singa 分组，但在更细分的标签（如 `非touchtown`）中会被单独处理 [2][18]。*

*   **Test (测试):**
    *   定义为 `risk_source = 6` [2][18]。

*   **Refuse (拒绝分组):**
    *   定义为 `risk_source = 4` [2]。

*   **Other (其他):**
    *   定义为 `risk_source` 不属于上述主要类别（如不属于 0, 2, 5, 6）的流量 [18]。

### 2. 计算公式

无论分组标签如何，基于上述标签过滤后的数据，通过率的具体计算公式保持一致：

*   **分子（Loan RC passed）**：在特定标签分组下，`type = 0`（提交申请）且 `machine_status = 1`（机器审核通过）的去重订单数。
*   **分母（Loan submitted）**：在特定标签分组下，`type = 0` 的去重订单总数。
*   **结果**：`( 分子 / 分母 ) * 100`，通常保留两位小数 [2][4][6]。

### References

* [1] Query1637:风控通过量分时
* [2] Query1227:Singa Loan T1 000 RC overview
* [4] Query711:9月10号事故订单监控
* [6] Query949:Singa复借（2024年3月后）
* [18] Query272:Loan overview T1

## Q20:B2B 和 B2C 商户交易数据分别存在哪些表？如何区分？

## R20：
基于提供的上下文信息，B2B（商户端）和 B2C（用户端）的交易数据分别存储在不同的源表中，且通过特定的业务逻辑进行区分。

以下是详细的数据来源与区分方式：

### 1. B2C 交易数据（面向用户）

B2C 交易主要涉及个人用户的余额变动、充值（Top Up）、转账（Transfer）和账单支付（PPOB）。

*   **核心数据表：**
    *   **`top_up_histories` (Money In)**：用于记录 B2C 的充值交易（如 VA Top Up）。在 B2C 分类中，它被标记为 "VA b2c" 或 "Money In" [6][15]。
    *   **`transfer_histories` (Money Out)**：用于记录 B2C 的转账交易，包括提现到银行账户（Money Out - Bank Account）和用户间转账（Money Out - Fellow User）[4][6][15]。
    *   **`bill_payment_histories`**：用于记录 PPOB（支付点在线银行）交易历史 [6]。
    *   **`qris_histories`**：专门用于记录 B2C 的 QRIS 交易（Money In/QRIS），注意这里使用的是 `_histories` 后缀 [6]。
    *   **`customer_statements`**：用于记录用户层面的流水账单，字段包括用户余额（User Balance）、交易类型（Credit/Debit）等 [4]。

*   **区分特征：**
    *   交易通常与 `user_id` 或个人用户余额 (`balance_after`) 关联 [4]。
    *   资金流向被分类为 "Money In"（通过 `top_up_histories` 和 `qris_histories`）和 "Money Out"（通过 `transfer_histories`）[6]。

### 2. B2B 交易数据（面向商户）

B2B 交易主要涉及商户收款、支付链接、批量付款（Disbursement）和结算（Settlement）。

*   **核心数据表：**
    *   **`qris_transactions`**：用于记录 B2B 的 QRIS 交易。与 B2C 不同，B2B 使用 `_transactions` 表 [1][2][3]。
    *   **`va_transactions`**：用于记录商户端的虚拟账户（VA）交易（VA B2B）[1][2][3]。
    *   **`payment_link_histories`**：用于记录支付链接产生的交易（包含 QRIS 和 VA 方式），被标记为 "payment_links b2b" [1][2]。
    *   **`settlements`**：记录商户的资金结算（Settlement B2B），通常涉及将资金结算到商户银行账户 [1][2][3]。
    *   **`bulk_disbursement_details`** 和 **`disbursements`**：用于记录 B2B 的批量或单笔代付/下发业务（Disburse B2B）[1][2][3]。
    *   **`manual_top_ups`**：用于记录商户端的手动充值操作（Manual Top Up B2B）[1][2]。

*   **区分特征：**
    *   数据通常直接关联 `merchant_id` 或 `merchant_no`，并涉及商户账户 (`accounts`) 关联 [3]。
    *   交易类型包括商户特有的 "Disburse"（代付）和 "Settlement"（结算）[1]。

### 3. 如何区分 B2B 与 B2C

主要通过 **表名后缀** 和 **业务场景** 进行区分：

1.  **QRIS 交易：**
    *   **B2C** 存放在 `qris_histories` [6]。
    *   **B2B** 存放在 `qris_transactions` [1][2]。

2.  **虚拟账户/充值（VA/Top Up）：**
    *   **B2C** 存放在 `top_up_histories` [15]。
    *   **B2B** 存放在 `va_transactions` [1]。

3.  **资金汇出（Money Out）：**
    *   **B2C** 使用 `transfer_histories`（分为转账给用户或银行）[15]。
    *   **B2B** 使用 `disbursements`（代付）或 `settlements`（结算）[1]。

4.  **业务逻辑标签：**
    *   在报表逻辑中，B2C 数据源常被硬编码标记为 `'VA b2c'`, `'transfer b2c'`, `'ppob b2c'` [15]。
    *   B2B 数据源常被标记为 `'va b2b'`, `'qris b2b'`, `'disburse b2b'`, `'settlement b2b'` [1]。

### References

- [1] Query1981:B2B Cost to vendor
- [2] Query1986:PG - Singapay Monitor Daily - B2B
- [3] Query1988:PG - Singapay Monitor Monthly - B2B
- [4] Query1763:PG - Singapay B2C
- [6] Query2025:Merchant Transaction B2C