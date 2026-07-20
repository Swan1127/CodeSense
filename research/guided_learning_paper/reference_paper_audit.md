# 外部论文参照审计

核验日期：2026年7月20日。核验材料为用户提供的11篇PDF；题名、作者、出版信息、样本和方法均以PDF全文为准。PDF未给出的卷期、页码、DOI或正式出版信息不补写。这里的“直接参照”指可用于界定本文的比较对象或写作边界，不表示可直接比较效果。

## 固定来源集与使用规则

后续两篇正文优先使用“直接参照”的四篇文献来界定外部比较对象；“方法参照”仅用于说明智能体设计、模拟或评估的方法背景；“不建议写入正文”的三篇默认不引用。所有来源都不能把本文的日志相关、阶段完成或重复使用解释为学习增益或因果效果。

本文中的智能体边界如下：教师型Agent在会话内对学生回答提供提示；虚拟学生在会话内接受讲解、追问并给出待修正代码。它们服务于真实学生的学习活动，不是跨作业保存画像、替代学生行为或生成合成学习数据的学习者模拟器。

## 直接参照

### 1. Impact of AI-agent-supported collaborative learning on the learning outcomes of University programming courses

- **作者与出版信息：** Haoming Wang、Chengliang Wang、Zhan Chen、Fa Liu、Chunjia Bao、Xianlong Xu；*Education and Information Technologies*，30，17717-17749（2025），DOI `10.1007/s10639-025-13487-8`。
- **研究对象与设计：** 上海某高校45名本科生，在ACM程序设计竞赛教学情境中开展6周、每周70分钟的准实验；AI-CL实验组24人，CSCL对照组21人。
- **智能体定义：** 面向协作学习的LLM AI-Agent系统，用于向学生提供智能支持；论文讨论的是AI-CL教学安排，而非学习者模拟。
- **数据与评价：** 比较学习成绩、自我效能、认知负荷和学习兴趣。
- **可供本文借鉴的写法：** 将系统角色、教学活动、分组、周期、测量指标和比较条件分别说明；可作为程序设计课程AI智能体准实验的外部参照。
- **不可外推之处：** 本研究没有相同的实验组/控制组、前后测或学习结果测量，不能把本文的会话、阶段日志或提交关联与该文的组间结果并列为效果证据。

### 2. Agent4Edu: Generating Learner Response Data by Generative Agents for Intelligent Education Systems

- **作者与出版信息：** Weibo Gao、Qi Liu、Linan Yue、Fangzhou Yao、Rui Lv、Zheng Zhang、Hao Wang、Zhenya Huang；AAAI-25。所核PDF未给出DOI、卷期或页码。
- **研究对象与设计：** 基于EduData的计算实验；数据含500名中国高中生在数学、物理中的18,045条有时间顺序的作答记录。
- **智能体定义：** 以学习者画像、记忆和行动模块构成的生成式学习者代理，用来模拟练习理解、分析和作答，并与个性化学习算法交互。
- **数据与评价：** 检验模拟响应与真人学习者的一致性，并用模拟器评估和改进个性化学习算法。
- **可供本文借鉴的写法：** 清楚区分真实响应数据、合成响应和算法评测；在写智能体时交代画像、记忆、行动及其评价目标。
- **不可外推之处：** Agent4Edu的目标是学习者模拟与离线算法评估，不是引导真实学生完成程序设计活动；不能把其模拟智能体与本文会话内的教师型Agent或虚拟学生混为一谈。

### 3. Classroom Simulacra: Building Contextual Student Generative Agents in Online Education for Learning Behavioral Simulation

- **作者与出版信息：** Songlin Xu、Hao-Ning Wen、Hongyi Pan、Dallas Dominguez、Dongyin Hu、Xinyu Zhang；CHI '25，Yokohama，ACM，26页，DOI `10.1145/3706598.3713773`。
- **研究对象与设计：** 6周在线教育工作坊，60名学生、8名教师；记录12次、每次1小时的学习活动和细粒度课程材料标注，并用这些记录评估模拟能力。
- **智能体定义：** 带有可迁移迭代反思模块的上下文学生生成式代理，学习学生历史和课程材料对行为的影响，以模拟学习行为。
- **数据与评价：** 以真实学生学习记录为参照，比较提示式和微调式LLM及经典深度模型的行为模拟准确性与动态捕捉能力。
- **可供本文借鉴的写法：** 把课程材料、时间序列和行为粒度写清楚；可以借鉴其将“真实记录”与“模拟输出”分层报告的做法。
- **不可外推之处：** 该文的学习者模拟目标是建立可供教师试验的虚拟课堂，不能据此把本文真实学生在会话内接受引导的行为视为模拟结果，也不能据此推断本文的教学效果。

### 4. Pedagogical AI conversational agents in higher education: a conceptual framework and survey of the state of the art

- **作者与出版信息：** Habeeb Yusuf、Arthur Money、Damon Daylamani-Zad；*Educational Technology Research and Development*，73，815-874（2025），DOI `10.1007/s11423-025-10447-4`。
- **研究对象与设计：** 高等教育教学型AI对话智能体文献；纳入92篇文献，采用主题模板分析，并据此提出概念框架。
- **智能体定义：** 从教学应用、教学目的、学习模式和意图，以及具身性、功能类型和特征等维度界定教学型对话智能体。
- **数据与评价：** 评价对象是文献主题与框架覆盖，而非某一课堂中学生的学习变化。
- **可供本文借鉴的写法：** 用角色、用途、交互方式和技术功能描述对话智能体，而不以“Agent”这一名称代替教学任务说明。
- **不可外推之处：** 综述和概念框架不能证明本文教师型Agent或虚拟学生更有效，也不能替代对对话质量、学生理解或学习结果的实测。

## 方法参照

### 5. LLM Agents for Education: Advances and Applications

- **作者与出版信息：** Zhendong Chu、Shen Wang、Jian Xie、Tinghui Zhu、Yibo Yan、Jinheng Ye、Aoxiao Zhong、Xuming Hu、Jing Liang、Philip S. Yu、Qingsong Wen；*Findings of the Association for Computational Linguistics: EMNLP 2025*，13782-13810。
- **研究对象与设计：** 教育场景LLM Agents的综述，覆盖反馈生成、课程设计、数据集、基准与算法框架。
- **智能体定义：** 承担复杂教学任务的LLM Agent，关注技术能力、教育任务和部署问题。
- **数据与评价：** 综述不同系统、数据集和基准，不报告本文可直接复用的真实学生实验。
- **可供本文借鉴的写法：** 可用于核对教育Agent的任务边界、幻觉、依赖和与既有教学系统整合等问题。
- **不可外推之处：** 综述不能证明特定多智能体流程在本文课程中有效，也不能替代真实部署的过程证据。

### 6. EduPlanner: LLM-Based Multi-Agent Systems for Customized and Intelligent Instructional Design

- **作者与出版信息：** Xueqiao Zhang、Chao Zhang、Jianwen Sun、Jun Xiao、Yi Yang、Yawei Luo；所核PDF未标明正式出版信息或DOI。
- **研究对象与设计：** 以数学课教学设计为对象的系统论文；在GSM8K和Algebra数据集上进行计算实验和消融分析。
- **智能体定义：** 由评价Agent、优化Agent和题目分析Agent组成的对抗式协作系统，使用Skill-Tree建模学习群体的知识背景。
- **数据与评价：** 以CIDDP五维指标评价教学设计质量，比较组件配置和优化结果。
- **可供本文借鉴的写法：** 可借鉴把每个Agent的输入、职责、输出和评价维度拆开写，避免把“多智能体”写成笼统能力。
- **不可外推之处：** 该文评估教学设计生成，不涉及本文的真实学生会话、代码重构或跨作业采用，不能作为学习成效参照。

### 7. MEDCO: Medical Education Copilots Based on A Multi-Agent Framework

- **作者与出版信息：** Hao Wei、Jianing Qiu、Haibao Yu、Wu Yuan；所核PDF未标明正式出版信息或DOI。
- **研究对象与设计：** 医学教育中的多智能体副驾驶系统；用虚拟学生训练和医学任务实验检验框架。
- **智能体定义：** 由患者、专家医生和放射科医生构成的多智能体环境，模拟医学训练中的多学科、交互式情境。
- **数据与评价：** 报告虚拟学生的训练表现、人类式学习行为，以及不同学习样本量下的模型结果。
- **可供本文借鉴的写法：** 可借鉴角色职责和交互回合的显式描述，特别是说明谁提出问题、谁给出反馈、谁完成判断。
- **不可外推之处：** 医学虚拟训练和模型表现不能证明本文虚拟学生对真实程序设计学生的影响；其学科任务、参与者和结果指标均不同。

### 8. SEFL: A Framework for Generating Synthetic Educational Assignment Feedback with LLM Agents

- **作者与出版信息：** Mike Zhang、Amalie Pernille Dilling、Léon Gondelman、Niels Erik Ruan Lyngdorf、Euan D. Lindsay、Johannes Bjerva；所核PDF未标明正式出版信息或DOI。
- **研究对象与设计：** 用教师—学生角色的两个LLM生成作业与形成性反馈，构建19.8K组合成样本；在900个输出上由3个LLM评审和3位人类专家评价。
- **智能体定义：** 教师角色负责批评与改进建议，学生角色模拟作业完成，用于生成合成反馈训练数据。
- **数据与评价：** 比较微调模型、未微调模型和基线的反馈质量，并报告人类与LLM评审。
- **可供本文借鉴的写法：** 可借鉴把合成数据、模型评审和人工评审分开报告，并交代反馈生成的评价单位。
- **不可外推之处：** 合成作业—反馈对及其质量评分不等于学生学习过程；不能用于解释本文真实学生的会话完成、对话轮次或代码提交。

## 不建议写入正文

### 9. AAAR-1.0: Assessing AI's Potential to Assist Research

- **作者与出版信息：** Renze Lou等；第42届国际机器学习会议（ICML 2025），PMLR 267；所核PDF未见DOI。
- **研究对象与设计：** 面向研究工作的LLM基准，覆盖公式推断、实验设计、论文弱点识别和评审批评四类任务。
- **智能体定义：** 评测的对象是通用LLM在研究任务上的能力，不是教育教学智能体。
- **数据与评价：** 在基准数据上比较开源与闭源模型表现。
- **可供本文借鉴的写法：** 若后续专门讨论AI辅助研究或论文评审，可借鉴其任务拆分和基准报告方式。
- **不可外推之处：** 与程序设计教学、学生引导和课堂过程数据无直接对应，不应作为本文智能体设计或教育效果的来源。

### 10. The role of large language models in personalized learning: a systematic review of educational impact

- **作者与出版信息：** Sahil Sharma、Puneet Mittal、Mukesh Kumar、Vivek Bhardwaj；*Discover Sustainability*，6，243（2025），DOI `10.1007/s43621-025-01094-z`。
- **研究对象与设计：** 2020-2024年间55项LLM个性化学习研究的系统综述，讨论参与、情感与社会发展、进度监测、考试、公平与伦理。
- **智能体定义：** 讨论LLM学习系统的个性化能力，不针对本文所用的教师型Agent或虚拟学生角色。
- **数据与评价：** 对纳入文献进行系统性归纳和质量评估。
- **可供本文借鉴的写法：** 若需要概述个性化、隐私、公平或伦理议题，可作为背景核对线索。
- **不可外推之处：** 综述范围宽，不能支持本文三阶段活动的独特性、真实课堂成效或平台日志的具体解释；默认不写入正文。

### 11. MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making

- **作者与出版信息：** Yubin Kim、Chanwoo Park、Hyewon Jeong、Yik Siu Chan、Xuhai Xu、Daniel McDuff、Hyeonhoon Lee、Marzyeh Ghassemi、Cynthia Breazeal、Hae Won Park；NeurIPS 2024；所核PDF首页标注arXiv:2404.15155v3，未见DOI。
- **研究对象与设计：** 医疗知识、诊断与多模态推理基准上的计算实验；框架先判断任务复杂度，再安排单人或群体协作。
- **智能体定义：** 主持者负责分诊和组织，按任务需要招募专家Agent并汇总决策。
- **数据与评价：** 在10个医学基准上比较准确率、效率和消融结果，并将复杂度判断与医生标注比较。
- **可供本文借鉴的写法：** 若后续确有必要讨论动态协作结构，可借鉴其把路由、角色分配和汇总步骤分别验证的思路。
- **不可外推之处：** 医疗决策基准与教育活动无关；不能用其模型准确率、专家标注或多智能体调度来论证本文教学设计。

## 审计结论

本文的外部比较重点应放在“真实程序设计课堂中的AI-Agent准实验”与“教育对话智能体的角色边界”上。Agent4Edu和Classroom Simulacra可用于说明学习者模拟的目标和验证方式，但必须明确它们模拟的是学习者行为；本文记录的对象则是真实学生在会话内完成、退出或跨作业复用三阶段活动的过程。正文不把这两类证据相互替代。
