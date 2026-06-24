/**
 * 三阶段引导式学习系统 — 前端交互逻辑
 * Guided Learning Arena (thinking.js)
 */

(function () {
    'use strict';

    // ============================================================
    // State Management
    // ============================================================
    const state = {
        sessionId: null,
        assignmentId: null,
        currentStage: 1,
        preset: null,
        // Timer
        startTime: null,
        timerInterval: null,
        // Stage 1
        stage1Score: null,
        // Stage 2
        solutionBlocks: [],
        poolSortable: null,
        solutionSortable: null,
        // Stage 3
        teacherMessages: [],
        studentMessages: [],
        feynmanPhase: 'chat', // 'chat' | 'code_review' | 'completed'
        buggyCode: null,
        // Flags
        isLoading: false,
    };

    // ============================================================
    // Initialization
    // ============================================================
    function init() {
        const container = document.getElementById('arena-container');
        if (!container) return;

        state.assignmentId = parseInt(container.dataset.assignmentId);
        const presetStatus = (container.dataset.presetStatus || '').trim();

        if (presetStatus !== 'ready') {
            if (presetStatus === 'generating') {
                pollPresetStatus();
            }
            return;
        }

        startTimer();
        startSession();
    }

    function pollPresetStatus() {
        const interval = setInterval(() => {
            fetchJSON(`/thinking/api/preset_status/${state.assignmentId}`, { method: 'GET' })
                .then(data => {
                    if (data.status === 'ready' || data.status === 'failed') {
                        clearInterval(interval);
                        location.reload();
                    }
                })
                .catch(err => console.error('轮询预设状态失败:', err));
        }, 3000);
    }

    function startSession() {
        setLoading(true);
        fetchJSON('/thinking/api/start_session', {
            method: 'POST',
            body: JSON.stringify({ assignment_id: state.assignmentId })
        }).then(data => {
            if (data.success) {
                state.sessionId = data.session_id;
                state.currentStage = data.current_stage;
                state.preset = data.preset;

                if (data.resumed) {
                    showNotification('已恢复上次的学习进度', 'info');
                    state.isResumed = true;
                    state.elapsedSeconds = data.elapsed_seconds || 0;
                    state.stage1Description = data.stage1_description || '';
                    state.stage1Score = data.stage1_score || null;
                    state.stage2BlockOrder = data.stage2_block_order || null;
                    state.companionHistory = data.companion_history || [];
                    state.teacherHistory = data.teacher_history || [];
                    state.studentHistory = data.student_history || [];
                    state.buggyCodeInfo = data.buggy_code_info || null;

                    // 同步并重新启动计时器
                    if (state.timerInterval) {
                        clearInterval(state.timerInterval);
                    }
                    state.startTime = Date.now() - state.elapsedSeconds * 1000;
                    startTimer();
                }

                initStage(state.currentStage);
            } else {
                showError(data.error || '创建会话失败');
            }
        }).catch(err => {
            showError('连接服务器失败: ' + err.message);
        }).finally(() => setLoading(false));
    }

    // ============================================================
    // Stage Navigation
    // ============================================================
    function initStage(stage) {
        state.currentStage = stage;
        updateProgressUI(stage);

        document.querySelectorAll('.stage-section').forEach(s => s.classList.remove('active'));
        const target = document.getElementById(`stage-${stage}`);
        if (target) target.classList.add('active');

        // Update body layout for stage 3
        const body = document.querySelector('.arena-body');
        if (body) {
            body.classList.toggle('feynman-layout', stage === 3);
        }

        if (stage === 1) initStage1();
        else if (stage === 2) initStage2();
        else if (stage === 3) initStage3();
    }

    function updateProgressUI(currentStage) {
        for (let i = 1; i <= 3; i++) {
            const circle = document.getElementById(`step-circle-${i}`);
            const label = document.getElementById(`step-label-${i}`);
            const line = document.getElementById(`step-line-${i}`);

            if (circle) {
                circle.classList.remove('active', 'completed');
                if (i < currentStage) circle.classList.add('completed');
                else if (i === currentStage) circle.classList.add('active');
            }
            if (label) {
                label.classList.remove('active', 'completed');
                if (i < currentStage) label.classList.add('completed');
                else if (i === currentStage) label.classList.add('active');
            }
            if (line) {
                line.classList.remove('completed');
                if (i < currentStage) line.classList.add('completed');
            }
        }
    }

    // ============================================================
    // Stage 1: Natural Language Description
    // ============================================================
    function initStage1() {
        const textarea = document.getElementById('description-input');
        const submitBtn = document.getElementById('stage1-submit');
        const hintBtn = document.getElementById('stage1-hint');

        if (submitBtn) {
            submitBtn.onclick = () => submitDescription();
        }
        if (hintBtn) {
            hintBtn.onclick = () => requestStage1Hint();
        }
        if (textarea) {
            textarea.focus();
            if (state.isResumed && state.stage1Description) {
                textarea.value = state.stage1Description;
            }
        }

        // Setup algorithm summary collapse toggle & display
        const algoSummaryWrapper = document.getElementById('algo-summary-wrapper');
        const algoSummaryContent = document.getElementById('algo-summary-content');
        const algoSummaryIcon = document.getElementById('algo-summary-icon');
        const algoSummaryHeader = document.getElementById('algo-summary-header');
        const stage1Instruction = document.getElementById('stage1-instruction');

        if (state.preset && state.preset.algorithm_summary) {
            if (algoSummaryWrapper) {
                algoSummaryWrapper.style.display = 'block';
            }
            if (algoSummaryContent) {
                algoSummaryContent.innerText = state.preset.algorithm_summary;
                algoSummaryContent.style.display = 'block'; // Default expanded
            }
            if (algoSummaryIcon) {
                algoSummaryIcon.className = 'bi bi-chevron-up';
            }
            if (stage1Instruction) {
                stage1Instruction.style.display = 'flex';
            }
        } else {
            if (algoSummaryWrapper) algoSummaryWrapper.style.display = 'none';
            if (stage1Instruction) stage1Instruction.style.display = 'none';
        }

        if (algoSummaryHeader) {
            algoSummaryHeader.onclick = () => {
                if (algoSummaryContent) {
                    if (algoSummaryContent.style.display === 'none') {
                        algoSummaryContent.style.display = 'block';
                        if (algoSummaryIcon) algoSummaryIcon.className = 'bi bi-chevron-up';
                    } else {
                        algoSummaryContent.style.display = 'none';
                        if (algoSummaryIcon) algoSummaryIcon.className = 'bi bi-chevron-down';
                    }
                }
            };
        }

        // Setup guided questions display
        const questionsWrapper = document.getElementById('guided-questions-wrapper');
        const questionsList = document.getElementById('guided-questions-list');
        const questions = (state.preset && state.preset.guided_questions && state.preset.guided_questions.length > 0)
            ? state.preset.guided_questions
            : [
                "本题需要设计几个循环？循环的截止条件是什么？",
                "需要使用哪些辅助数据结构或变量（如数组、小根堆、指针等）？",
                "输入数据的读取和输出结果的打印如何对应到算法流程中？"
            ];

        if (questionsWrapper && questionsList) {
            questionsList.innerHTML = '';
            questions.forEach(q => {
                const li = document.createElement('li');
                li.innerText = q;
                questionsList.appendChild(li);
            });
            questionsWrapper.style.display = 'block';
        }

        // Initialize dynamic companion chat greeting for Stage 1
        const container = document.getElementById('companion-messages');
        if (container) {
            container.innerHTML = '';
            state.companionMessages = [];
            
            if (state.isResumed && state.companionHistory && state.companionHistory.length > 0) {
                state.companionHistory.forEach(msg => {
                    appendCompanionMessage(msg.content, msg.role === 'student' ? 'student' : 'ai');
                    state.companionMessages.push({ role: msg.role === 'student' ? 'user' : 'assistant', content: msg.content });
                });
            } else {
                const problemTitle = document.querySelector('.problem-panel h2')?.innerText?.replace(/[\r\n]/g, '').replace('引导式学习 - ', '').trim() || '当前任务';
                
                let greeting = `哈罗！我是你的 AI 伴学助手。我们今天的任务是完成《${problemTitle}》。\n\n`;
                if (state.preset && state.preset.algorithm_summary) {
                    greeting += `我已为你准备好了这道题的标准算法步骤简述（见左侧「算法思路参考」）。\n\n为了帮你理清思路，你可以尝试思考并回答以下引导问题：\n`;
                } else {
                    greeting += `为了帮你理清思路，你可以尝试思考并回答以下引导问题：\n`;
                }
                
                questions.forEach((q, i) => {
                    greeting += `${i + 1}️⃣ **${q}**\n`;
                });
                
                greeting += `\n你可以结合左侧的算法流程和上面的引导提问，用自己的语言把解题步骤描述出来并提交。你也可以直接在下方回答这些问题，我会引导你完善成合格的思路描述哦！加油！✨`;
                
                appendCompanionMessage(greeting, 'ai');
            }
        }
    }

    function submitDescription() {
        const textarea = document.getElementById('description-input');
        const description = textarea ? textarea.value.trim() : '';

        if (description.length < 5) {
            showNotification('请至少写5个字的思路描述', 'warning');
            return;
        }

        // Show loading state on submit button to prevent "frozen" feeling
        const submitBtn = document.getElementById('stage1-submit');
        const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split rotating-icon"></i> 正在评判中，请稍候...';
        }
        if (textarea) textarea.disabled = true;

        setLoading(true);
        fetchJSON('/thinking/api/stage1/submit', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                description: description
            })
        }).then(data => {
            if (data.success) {
                state.stage1Score = data.score;
                showScoreResult(data.score, data.feedback, data.passed);

                if (data.passed) {
                    showNotification('🎉 思路描述通过！进入积木编程阶段', 'success');
                    setTimeout(() => initStage(2), 1500);
                } else {
                    // Proactively post AI Companion guidance
                    appendCompanionMessage(`我看到你的思路描述匹配度为 ${data.score}%，还差一点就达到 60% 的通过标准啦！\n导师点评说："${data.feedback}"\n\n别灰心，你可以根据点评修改你的思路。如果你修改有困难，可以尝试问我："我该如何写这道题的输入/循环/输出部分？"，或者直接点击左侧下方的【请求提示】按钮，我会给你更明确的思路大纲！`, 'ai');
                }
            }
        }).catch(err => showError(err.message))
          .finally(() => {
            setLoading(false);
            // Restore submit button and textarea
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHtml;
            }
            if (textarea) textarea.disabled = false;
          });
    }

    function showScoreResult(score, feedback, passed) {
        const container = document.getElementById('score-result');
        if (!container) return;

        container.innerHTML = `
            <div class="score-display">
                <div class="score-circle ${passed ? 'pass' : 'fail'}">${score}%</div>
                <div class="score-feedback">${feedback}</div>
            </div>
        `;
        container.style.display = 'block';
    }

    function requestStage1Hint() {
        const textarea = document.getElementById('description-input');
        const description = textarea ? textarea.value.trim() : '';

        setLoading(true);
        // Route hint request through AI Companion chat
        appendCompanionMessage('我在撰写思路描述时遇到困难，请给我一些引导提示。', 'student');

        fetchJSON('/thinking/api/stage1/hint', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                description: description
            })
        }).then(data => {
            if (data.success) {
                appendCompanionMessage(data.hint, 'ai');
                if (!state.companionMessages) state.companionMessages = [];
                state.companionMessages.push({ role: 'user', content: '我在撰写思路描述时遇到困难，请给我一些引导提示。' });
                state.companionMessages.push({ role: 'assistant', content: data.hint });
            }
        }).catch(err => showError(err.message))
          .finally(() => setLoading(false));
    }

    // ============================================================
    // Stage 2: Block Puzzle (Parsons Problem)
    // ============================================================
    function initStage2() {
        if (!state.preset || !state.preset.blocks) {
            showError('积木数据未加载');
            return;
        }

        state.companionMessages = [];
        
        // 恢复伴学助手聊天记录
        if (state.isResumed && state.companionHistory && state.companionHistory.length > 0) {
            const container = document.getElementById('companion-messages');
            if (container) {
                container.innerHTML = '';
                state.companionHistory.forEach(msg => {
                    appendCompanionMessage(msg.content, msg.role === 'student' ? 'student' : 'ai');
                    state.companionMessages.push({ role: msg.role === 'student' ? 'user' : 'assistant', content: msg.content });
                });
            }
        } else {
            // Welcoming AI companion message for Stage 2
            const problemTitle = document.querySelector('.problem-panel h2')?.innerText?.replace(/[\r\n]/g, '').replace('引导式学习 - ', '').trim() || '当前任务';
            const greeting = `太棒了！第一阶段的思路描述顺利通关！🎉\n\n接下来是第二阶段：**积木编程**。我们需要把刚才的解题思路，用代码块拼装出来：\n1️⃣ **看清需求**：仔细阅读左侧【散落池】中每个代码块的代码和文字标签。\n2️⃣ **拖拽组合**：把需要的积木拖到右侧构建区。注意，为了让你专注于核心算法流程，外部的 \`#include\` 头文件和 \`main()\` 框架已经帮你包裹好啦，你只需要拼装核心逻辑。\n3️⃣ **注意陷阱**：散落池里有些代码块是会误导你的**“噪声块”**（比如写错了循环边界或运算符），千万不要把它们拖进去哦！\n4️⃣ **调整缩进**：拼好顺序后，别忘了点击积木的 ◀ ▶ 按钮调整缩进层级（或者点击构建区右上角的【一键大括号嵌套】让我帮你自动对齐）。\n\n拼装过程中遇到任何阻碍，随时可以点击【请求提示】或者直接在下面发消息问我！比如你可以问我：\n- “我的代码块顺序拼对了吗？”\n- “这几个积木分别有什么作用？”\n- “为什么我总是验证不通过？”`;
            appendCompanionMessage(greeting, 'ai');
        }

        // 恢复积木的拼装和散落状态
        if (state.isResumed && state.stage2BlockOrder && state.stage2BlockOrder.length > 0) {
            const solution = document.getElementById('block-solution-list');
            if (solution) {
                solution.innerHTML = '';
                const blockMap = {};
                state.preset.blocks.forEach(b => {
                    blockMap[b.id] = b;
                });
                state.stage2BlockOrder.forEach(item => {
                    const block = blockMap[item.id];
                    if (block) {
                        const el = createBlockElement(block);
                        el.dataset.indent = item.indent || 0;
                        el.style.marginLeft = `${(item.indent || 0) * 24}px`;
                        solution.appendChild(el);
                    }
                });
            }

            const pool = document.getElementById('block-pool-list');
            if (pool) {
                const solutionIds = state.stage2BlockOrder.map(item => item.id);
                const remainingBlocks = state.preset.blocks.filter(b => !solutionIds.includes(b.id));
                const shuffled = [...remainingBlocks];
                for (let i = shuffled.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
                }
                pool.innerHTML = '';
                shuffled.forEach(block => {
                    const el = createBlockElement(block);
                    pool.appendChild(el);
                });
            }
        } else {
            renderPhasePool();
        }

        initSortable();
        updateBlockPreview();
    }

    function renderPhasePool() {
        const pool = document.getElementById('block-pool-list');
        if (!pool || !state.preset.blocks) return;

        // Fisher-Yates shuffle to thoroughly randomize block order in the pool
        const shuffled = [...state.preset.blocks];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }

        pool.innerHTML = '';
        shuffled.forEach(block => {
            const el = createBlockElement(block);
            pool.appendChild(el);
        });
    }


    function createBlockElement(block) {
        const div = document.createElement('div');
        div.className = 'code-block';
        div.dataset.blockId = block.id;
        div.dataset.indent = 0;
        div.innerHTML = `
            <code>${escapeHtml(block.code)}</code>
            <div class="block-label">${escapeHtml(block.label || '')}</div>
            <div class="indent-controls">
                <button class="indent-btn" onclick="window.ThinkingArena.decreaseIndent(this)" title="减少缩进">◀</button>
                <button class="indent-btn" onclick="window.ThinkingArena.increaseIndent(this)" title="增加缩进">▶</button>
            </div>
        `;
        return div;
    }

    function initSortable() {
        const pool = document.getElementById('block-pool-list');
        const solution = document.getElementById('block-solution-list');
        if (!pool || !solution) return;

        if (state.poolSortable) state.poolSortable.destroy();
        if (state.solutionSortable) state.solutionSortable.destroy();

        const sortableOptions = {
            group: 'blocks',
            animation: 200,
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
        };

        state.poolSortable = Sortable.create(pool, { ...sortableOptions });
        state.solutionSortable = Sortable.create(solution, {
            ...sortableOptions,
            onAdd: function () { updateBlockPreview(); },
            onUpdate: function () { updateBlockPreview(); },
            onRemove: function () { updateBlockPreview(); }
        });
    }

    function increaseIndent(btn) {
        const block = btn.closest('.code-block');
        if (!block) return;
        const current = parseInt(block.dataset.indent || 0);
        if (current < 4) {
            block.dataset.indent = current + 1;
            block.style.marginLeft = (current + 1) * 24 + 'px';
            updateBlockPreview();
        }
    }

    function decreaseIndent(btn) {
        const block = btn.closest('.code-block');
        if (!block) return;
        const current = parseInt(block.dataset.indent || 0);
        if (current > 0) {
            block.dataset.indent = current - 1;
            block.style.marginLeft = (current - 1) * 24 + 'px';
            updateBlockPreview();
        }
    }

    function updateBlockPreview() {
        let preview = '#include <iostream>\nusing namespace std;\nint main() {\n';
        let totalBlocks = 0;

        const solutionList = document.getElementById('block-solution-list');
        if (solutionList) {
            solutionList.querySelectorAll('.code-block').forEach(b => {
                totalBlocks++;
                preview += '    ' + '    '.repeat(parseInt(b.dataset.indent || 0)) + b.querySelector('code').textContent + '\n';
            });
        }

        preview += '    return 0;\n}';

        const previewEl = document.getElementById('code-preview');
        if (previewEl) {
            previewEl.textContent = totalBlocks > 0 ? preview : '// 从散落池依次拖入对应步骤的思维逻辑块...\n// 外部大括号结构已预填包裹';
        }
    }

    function autoNestBlocks() {
        const zone = document.getElementById('block-solution-list');
        if (!zone) return;

        const blocks = zone.querySelectorAll('.code-block');
        if (blocks.length === 0) {
            showNotification('核心构建区还是空的哦，请先拖入积木', 'warning');
            return;
        }

        const blockMap = {};
        if (state.preset && state.preset.blocks) {
            state.preset.blocks.forEach(b => {
                blockMap[b.id] = b.indent || 0;
            });
        }

        blocks.forEach(block => {
            const id = block.dataset.blockId;
            if (id && blockMap[id] !== undefined) {
                const targetIndent = blockMap[id];
                block.dataset.indent = targetIndent;
                block.style.marginLeft = targetIndent * 24 + 'px';
            }
        });

        updateBlockPreview();
        showNotification('✨ 代码缩进层级已对齐', 'success');
    }

    function verifyBlocks() {
        const zone = document.getElementById('block-solution-list');
        if (!zone) return;

        const blocks = zone.querySelectorAll('.code-block');
        const studentIds = Array.from(blocks).map(b => b.dataset.blockId);
        const studentIndents = Array.from(blocks).map(b => parseInt(b.dataset.indent || 0));

        const targetBlocks = state.preset.blocks
            .filter(b => !b.id.startsWith('noise-'))
            .sort((a, b) => parseInt(a.id) - parseInt(b.id));
        const targetIds = targetBlocks.map(b => b.id);
        const targetIndents = targetBlocks.map(b => b.indent || 0);

        if (studentIds.length === 0) {
            showNotification('请先拖入核心构建区所需的积木块', 'warning');
            appendCompanionMessage('提示：当前核心构建区还是空的哦！仔细看看左侧的算法块散落池，根据你的解题思路把核心积木块拖拽入中间的构建区吧！', 'ai');
            return;
        }

        const hasNoise = studentIds.some(id => id.startsWith('noise-'));
        if (hasNoise) {
            showNotification('混入了干扰思维的噪声块哦，结合上下文再思考一下', 'warning');
            appendCompanionMessage('提示：我发现你的构建区混入了带有陷阱的“噪声块”（比如写错运算符或少读了参数的无用代码块）。仔细对照思路，把不相关的噪声块移出构建区吧！如果想不通，可以在下方问我哦。', 'ai');
            return;
        }

        if (studentIds.length !== targetIds.length) {
            showNotification('积木数量不太对，思考一下是否遗漏或多余了', 'warning');
            appendCompanionMessage('提示：你拖入的积木块数量不太对。想一想，是不是漏掉了某些关键步骤？比如输入读取变量或者收尾计算输出？', 'ai');
            return;
        }

        let orderMatch = true;
        for (let i = 0; i < targetIds.length; i++) {
            if (studentIds[i] !== targetIds[i]) {
                orderMatch = false;
                break;
            }
        }

        if (!orderMatch) {
            showNotification('解题先后承接顺序还不准确，再调整一下顺序，或者向伴学助手发起对话理清逻辑', 'warning');
            appendCompanionMessage('提示：积木块的上下排列顺序不太正确。在程序执行中，通常遵循“定义与读取输入 -> 核心计算/循环 -> 条件判定 -> 打印结果”的先后承接关系。试着调整一下代码块的位置，或者向我提问理清逻辑！', 'ai');
            return;
        }

        let indentMatch = true;
        for (let i = 0; i < targetIndents.length; i++) {
            if (studentIndents[i] !== targetIndents[i]) {
                indentMatch = false;
                break;
            }
        }

        if (!indentMatch) {
            showNotification('积木顺序正确，但部分缩进层级需要调整，想想代码之间的嵌套关系？', 'warning');
            appendCompanionMessage('提示：太棒了！你的积木顺序已经完全正确了！但是有一些代码块的“缩进层级（左右对齐）”还不准确。例如循环体或者条件判断内部的代码通常需要往右缩进。你可以点击构建区右上角的【一键大括号嵌套】按钮，我来帮你对齐！', 'ai');
            return;
        }

        // Client-side passed! Now persist state on the backend
        setLoading(true);
        const blockOrder = Array.from(blocks).map(b => ({
            id: b.dataset.blockId,
            indent: parseInt(b.dataset.indent || 0)
        }));

        fetchJSON('/thinking/api/stage2/verify', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                block_order: blockOrder
            })
        }).then(data => {
            if (data.success && data.passed) {
                showNotification('🏆 积木拼接与逻辑缩进完美通关！进入费曼学习阶段', 'success');
                setTimeout(() => initStage(3), 1500);
            } else {
                showNotification(data.feedback || '验证失败，请重新检查', 'warning');
            }
        }).catch(err => {
            showError('同步学习进度失败: ' + err.message);
        }).finally(() => setLoading(false));
    }

    // Connect Stage 2 hints to backend API and companion chat
    function requestStage2Hint() {
        const zone = document.getElementById('block-solution-list');
        const blocks = zone ? zone.querySelectorAll('.code-block') : [];
        const currentBlockIds = Array.from(blocks).map(b => b.dataset.blockId);

        setLoading(true);
        appendCompanionMessage('我在进行积木编程拼接时遇到阻力，请给我一些引导提示。', 'student');

        fetchJSON('/thinking/api/stage2/hint', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                current_blocks: currentBlockIds
            })
        }).then(data => {
            if (data.success) {
                appendCompanionMessage(data.hint, 'ai');
                if (!state.companionMessages) state.companionMessages = [];
                state.companionMessages.push({ role: 'user', content: '我在进行积木编程拼接时遇到阻力，请给我一些引导提示。' });
                state.companionMessages.push({ role: 'assistant', content: data.hint });
            }
        }).catch(err => showError(err.message))
          .finally(() => setLoading(false));
    }

    function sendCompanionChat() {
        const input = document.getElementById('companion-chat-input');
        if (!input) return;
        const msgText = input.value.trim();
        if (!msgText) return;

        input.value = '';
        appendCompanionMessage(msgText, 'student');
        sendCompanionQueryStream(msgText);
    }

    function sendCompanionQueryStream(msgText) {
        const messages = state.companionMessages || [];
        messages.push({ role: 'user', content: msgText });
        state.companionMessages = messages;

        const container = document.getElementById('companion-messages');
        const typingId = 'typing-' + Date.now();
        if (container) {
            const typingDiv = document.createElement('div');
            typingDiv.className = 'chat-message';
            typingDiv.id = typingId;
            typingDiv.innerHTML = `
                <div class="chat-avatar teacher">🤖</div>
                <div class="chat-bubble ai"><span class="typing-dots">思考引导中...</span></div>
            `;
            container.appendChild(typingDiv);
            container.scrollTop = container.scrollHeight;
        }

        // 构造伴学对话请求体，注入当前的阶段及积木状态
        const requestBody = {
            session_id: state.sessionId,
            messages: messages,
            current_stage: state.currentStage
        };

        if (state.currentStage === 2) {
            const zone = document.getElementById('block-solution-list');
            const blocks = zone ? zone.querySelectorAll('.code-block') : [];
            const studentIds = Array.from(blocks).map(b => b.dataset.blockId);
            const studentIndents = Array.from(blocks).map(b => parseInt(b.dataset.indent || 0));

            // 获取期望的标准积木序列与缩进
            const targetBlocks = state.preset.blocks
                .filter(b => !b.id.startsWith('noise-'))
                .sort((a, b) => parseInt(a.id) - parseInt(b.id));
            const targetIds = targetBlocks.map(b => b.id);
            const targetIndents = targetBlocks.map(b => b.indent || 0);

            const hasNoise = studentIds.some(id => id.startsWith('noise-'));
            const lengthMismatch = studentIds.length > 0 && studentIds.length !== targetIds.length;
            
            let orderMatch = true;
            if (studentIds.length === targetIds.length) {
                for (let i = 0; i < targetIds.length; i++) {
                    if (studentIds[i] !== targetIds[i]) {
                        orderMatch = false;
                        break;
                    }
                }
            } else {
                orderMatch = false;
            }

            requestBody.stage2_state = {
                current_blocks: Array.from(blocks).map(b => ({
                    id: b.dataset.blockId,
                    code: b.querySelector('code')?.textContent || '',
                    label: b.querySelector('.block-label')?.textContent || '',
                    indent: parseInt(b.dataset.indent || 0)
                })),
                errors: {
                    is_empty: studentIds.length === 0,
                    has_noise: hasNoise,
                    length_mismatch: lengthMismatch,
                    order_match: orderMatch,
                    indent_match: orderMatch && (JSON.stringify(studentIndents) === JSON.stringify(targetIndents))
                }
            };
        }

        fetchJSON('/thinking/api/companion/chat', {
            method: 'POST',
            body: JSON.stringify(requestBody)
        }).then(data => {
            const typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();

            if (data.success) {
                messages.push({ role: 'assistant', content: data.response });
                appendCompanionMessage(data.response, 'ai');
            } else {
                appendCompanionMessage('连接错误，请重试。', 'ai');
            }
        }).catch(err => {
            const typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();
            appendCompanionMessage('连接服务器失败，请重试。', 'ai');
        });
    }

    function appendCompanionMessage(text, sender) {
        const container = document.getElementById('companion-messages');
        if (!container) return;

        const isUser = sender === 'student';
        const avatarClass = isUser ? 'student' : 'teacher';
        const avatarIcon = isUser ? '👤' : '🤖';

        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${isUser ? 'user' : ''}`;
        msgDiv.innerHTML = `
            <div class="chat-avatar ${avatarClass}">${avatarIcon}</div>
            <div class="chat-bubble ${isUser ? 'user-msg' : 'ai'}">${renderMarkdown(text)}</div>
        `;
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    }

    function regeneratePreset() {
        if (!confirm('确定要应用最新大括号归拢规范，重新拆解并生成当前作业的代码积木吗？')) return;

        const container = document.getElementById('arena-container');
        const assignmentId = container ? container.dataset.assignmentId : null;
        if (!assignmentId) return;

        setLoading(true);
        showNotification('正在应用全新整合规则重构积木池，请稍候...', 'info');

        fetchJSON('/thinking/api/generate_preset', {
            method: 'POST',
            body: JSON.stringify({ assignment_id: parseInt(assignmentId) })
        }).then(data => {
            if (data.success || data.status === 'ready') {
                showNotification('✨ 积木重构成功！正在重新加载版面', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('重构已触发，请稍后手动刷新', 'warning');
            }
        }).catch(err => showError(err.message))
          .finally(() => setLoading(false));
    }

    // ============================================================
    // Stage 3: Feynman Teaching (Dual Agent)
    // ============================================================
    function initStage3() {
        state.teacherMessages = [];
        state.studentMessages = [];
        state.feynmanPhase = 'chat';

        // 恢复老师辅导对话
        let restoredTeacher = false;
        if (state.isResumed && state.teacherHistory && state.teacherHistory.length > 0) {
            const container = document.getElementById('teacher-messages');
            if (container) {
                container.innerHTML = '';
                state.teacherHistory.forEach(msg => {
                    addChatMessage('teacher', msg.role, msg.content);
                    state.teacherMessages.push({ role: msg.role, content: msg.content });
                });
                restoredTeacher = true;
            }
        }
        if (!restoredTeacher) {
            addChatMessage('teacher', 'assistant',
                '你好！你已经完成了积木编程挑战，说明你对这道题有了不错的理解。现在我们来做一个更有趣的练习——你需要把你学到的东西教给你的同学小明（他刚开始学编程）。准备好了吗？');
        }

        // 恢复教学生（小明）对话
        let restoredStudent = false;
        if (state.isResumed && state.studentHistory && state.studentHistory.length > 0) {
            const container = document.getElementById('student-messages');
            if (container) {
                container.innerHTML = '';
                state.studentHistory.forEach(msg => {
                    addChatMessage('student', msg.role, msg.content);
                    state.studentMessages.push({ role: msg.role, content: msg.content });
                });
                restoredStudent = true;
            }
        }
        if (!restoredStudent) {
            addChatMessage('student', 'assistant',
                '嗨！听说你这道题做得很好，老师让你教教我😅 我刚开始学编程，你能给我讲讲这道题要怎么做吗？');
        }

        // 恢复代码修复面板
        if (state.isResumed && state.buggyCodeInfo) {
            state.feynmanPhase = 'code_review';
            state.buggyCode = state.buggyCodeInfo.buggy_code;
            showCodeReviewPanel(state.buggyCodeInfo.buggy_code);
        }
    }

    function sendTeacherChat() {
        const input = document.getElementById('teacher-chat-input');
        const message = input ? input.value.trim() : '';
        if (!message || state.isLoading) return;

        // Add user message to UI
        addChatMessage('teacher', 'user', message);
        state.teacherMessages.push({ role: 'user', content: message });
        input.value = '';

        // Show typing indicator
        showTypingIndicator('teacher');

        fetchJSON('/thinking/api/stage3/chat', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                messages: state.teacherMessages
            })
        }).then(data => {
            hideTypingIndicator('teacher');
            if (data.success) {
                addChatMessage('teacher', 'assistant', data.response);
                state.teacherMessages.push({ role: 'assistant', content: data.response });
            }
        }).catch(err => {
            hideTypingIndicator('teacher');
            showError(err.message);
        });
    }

    function sendStudentChat() {
        const input = document.getElementById('student-chat-input');
        const message = input ? input.value.trim() : '';
        if (!message || state.isLoading) return;

        addChatMessage('student', 'user', message);
        state.studentMessages.push({ role: 'user', content: message });
        input.value = '';

        showTypingIndicator('student');

        fetchJSON('/thinking/api/stage3/teach', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                messages: state.studentMessages
            })
        }).then(data => {
            hideTypingIndicator('student');
            if (data.success) {
                addChatMessage('student', 'assistant', data.response);
                state.studentMessages.push({ role: 'assistant', content: data.response });

                // Check if ready for code writing phase
                if (data.ready_for_code && state.feynmanPhase === 'chat') {
                    setTimeout(() => triggerCodeWritingPhase(), 2000);
                }
            }
        }).catch(err => {
            hideTypingIndicator('student');
            showError(err.message);
        });
    }

    function triggerCodeWritingPhase() {
        state.feynmanPhase = 'code_review';

        showTypingIndicator('student');

        fetchJSON('/thinking/api/stage3/write_code', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                messages: state.studentMessages
            })
        }).then(data => {
            hideTypingIndicator('student');
            if (data.success) {
                state.buggyCode = data.buggy_code;

                // Show the "bad student" message
                addChatMessage('student', 'assistant', data.message);
                state.studentMessages.push({ role: 'assistant', content: data.message });

                // Show code review panel
                showCodeReviewPanel(data.buggy_code);
            }
        }).catch(err => {
            hideTypingIndicator('student');
            showError(err.message);
        });
    }

    function showCodeReviewPanel(buggyCode) {
        const panel = document.getElementById('code-review-section');
        if (!panel) return;

        panel.innerHTML = `
            <div class="code-review-panel">
                <div class="code-review-header">
                    <i class="bi bi-exclamation-triangle"></i>
                    小明写的代码（老师说有问题）
                </div>
                <div class="code-review-body">
                    <pre><code>${escapeHtml(buggyCode)}</code></pre>
                    <textarea class="code-fix-input" id="code-fix-input"
                              placeholder="你可以修改代码，或者用文字描述哪里有问题、应该怎么改..."></textarea>
                    <div style="margin-top: 12px; display: flex; gap: 10px;">
                        <button class="arena-btn arena-btn-primary" onclick="window.ThinkingArena.submitCodeFix()">
                            <i class="bi bi-check2-circle"></i> 提交修复
                        </button>
                    </div>
                </div>
            </div>
        `;
        panel.style.display = 'block';

        // Pre-fill with buggy code for editing
        const fixInput = document.getElementById('code-fix-input');
        if (fixInput) {
            fixInput.value = buggyCode;
        }
    }

    function submitCodeFix() {
        const fixInput = document.getElementById('code-fix-input');
        const fixedCode = fixInput ? fixInput.value.trim() : '';

        if (!fixedCode) {
            showNotification('请修改代码或描述问题所在', 'warning');
            return;
        }

        setLoading(true);
        fetchJSON('/thinking/api/stage3/fix_code', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                buggy_code: state.buggyCode,
                fixed_code: fixedCode
            })
        }).then(data => {
            if (data.success) {
                if (data.correct) {
                    state.feynmanPhase = 'completed';
                    addChatMessage('student', 'assistant',
                        '哦！原来是这样！谢谢你帮我找出来了，我以后会注意的！🎉');
                    setTimeout(() => showCelebration(), 1000);
                    completeSession();
                } else {
                    showNotification(data.feedback || '修复不太对，再看看？', 'warning');
                    addChatMessage('student', 'assistant',
                        '嗯...我觉得好像还是不太对。你再帮我看看？' + (data.feedback ? '\n（' + data.feedback + '）' : ''));
                }
            }
        }).catch(err => showError(err.message))
          .finally(() => setLoading(false));
    }

    function completeSession() {
        const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
        fetchJSON('/thinking/api/complete_session', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                total_time_seconds: elapsed
            })
        });
    }

    // ============================================================
    // Chat UI Helpers
    // ============================================================
    function addChatMessage(panel, role, content) {
        const container = document.getElementById(`${panel}-messages`);
        if (!container) return;

        const isUser = role === 'user';
        const avatarClass = isUser ? 'student' : (panel === 'teacher' ? 'teacher' : 'bad-student');
        const avatarIcon = isUser ? '👤' : (panel === 'teacher' ? '👨‍🏫' : '🧑‍🎓');

        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${isUser ? 'user' : ''}`;
        msgDiv.innerHTML = `
            <div class="chat-avatar ${avatarClass}">${avatarIcon}</div>
            <div class="chat-bubble ${isUser ? 'user-msg' : 'ai'}">${renderMarkdown(content)}</div>
        `;
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    }

    function showTypingIndicator(panel) {
        const container = document.getElementById(`${panel}-messages`);
        if (!container) return;

        const existing = container.querySelector('.typing-indicator');
        if (existing) return;

        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.innerHTML = '<span></span><span></span><span></span>';
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function hideTypingIndicator(panel) {
        const container = document.getElementById(`${panel}-messages`);
        if (!container) return;
        const indicator = container.querySelector('.typing-indicator');
        if (indicator) indicator.remove();
    }

    // ============================================================
    // UI Helpers
    // ============================================================
    function showHint(hint, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const div = document.createElement('div');
        div.className = 'hint-bubble';
        div.innerHTML = `<i class="bi bi-lightbulb"></i><span>${renderMarkdown(hint)}</span>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function showNotification(message, type) {
        // Reuse Bootstrap toasts if available
        const toastContainer = document.querySelector('.toast-container');
        if (toastContainer && typeof bootstrap !== 'undefined') {
            const toastEl = document.createElement('div');
            toastEl.className = `toast toast-${type}`;
            toastEl.setAttribute('role', 'alert');
            toastEl.innerHTML = `
                <div class="toast-header">
                    <strong class="me-auto">${type === 'success' ? '✅' : type === 'warning' ? '⚠️' : 'ℹ️'}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">${message}</div>
            `;
            toastContainer.appendChild(toastEl);
            const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
            toast.show();
            return;
        }
        // Fallback
        console.log(`[${type}] ${message}`);
    }

    function showError(message) {
        showNotification(message, 'danger');
    }

    function showCelebration() {
        const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;

        const overlay = document.createElement('div');
        overlay.className = 'celebration-overlay';
        overlay.innerHTML = `
            <div class="celebration-card">
                <div class="celebration-icon">🏆</div>
                <div class="celebration-title">三阶段学习完成！</div>
                <div class="celebration-subtitle">
                    你成功完成了思路描述、积木编程和费曼教学三个阶段。<br>
                    总用时: ${minutes}分${seconds}秒
                </div>
                <button class="arena-btn arena-btn-success" onclick="this.closest('.celebration-overlay').remove()">
                    <i class="bi bi-check-lg"></i> 完成
                </button>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    function setLoading(isLoading) {
        state.isLoading = isLoading;
        document.querySelectorAll('.arena-btn-primary, .arena-btn-send').forEach(btn => {
            btn.disabled = isLoading;
        });
    }

    // ============================================================
    // Timer
    // ============================================================
    function startTimer() {
        if (!state.startTime) {
            state.startTime = Date.now();
        }
        state.timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
            const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const s = String(elapsed % 60).padStart(2, '0');
            const el = document.getElementById('arena-timer');
            if (el) el.textContent = `${m}:${s}`;
        }, 1000);
    }

    // ============================================================
    // Utilities
    // ============================================================
    function fetchJSON(url, options = {}) {
        return fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            }
        }).then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        });
    }

    function renderMarkdown(str) {
        if (!str) return '';
        if (typeof marked !== 'undefined') {
            marked.setOptions({ breaks: true, gfm: true });
            let html = marked.parse(str);
            if (typeof DOMPurify !== 'undefined') {
                html = DOMPurify.sanitize(html);
            }
            return html;
        }
        return escapeHtml(str).replace(/\n/g, '<br>');
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ============================================================
    // Public API (for onclick handlers in HTML)
    // ============================================================
    window.ThinkingArena = {
        init,
        submitDescription,
        requestStage1Hint,
        verifyBlocks,
        requestStage2Hint,
        regeneratePreset,
        autoNestBlocks,
        sendCompanionChat,
        sendTeacherChat,
        sendStudentChat,
        submitCodeFix,
        increaseIndent,
        decreaseIndent,
    };

    // Auto-init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
