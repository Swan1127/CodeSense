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
        startTime: Date.now(),
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
        }
    }

    function submitDescription() {
        const textarea = document.getElementById('description-input');
        const description = textarea ? textarea.value.trim() : '';

        if (description.length < 5) {
            showNotification('请至少写5个字的思路描述', 'warning');
            return;
        }

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
                }
            }
        }).catch(err => showError(err.message))
          .finally(() => setLoading(false));
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
        fetchJSON('/thinking/api/stage1/hint', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                description: description
            })
        }).then(data => {
            if (data.success) {
                showHint(data.hint, 'stage1-hints');
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

        state.currentSubPhase = 1;
        state.companionMessages = [];
        updateSubPhaseUI();
        renderPhasePool();
        initSortable();
        updateBlockPreview();
    }

    function updateSubPhaseUI() {
        const badge = document.getElementById('current-phase-badge');
        if (badge) badge.textContent = `步骤 ${state.currentSubPhase} / 3`;

        for (let p = 1; p <= 3; p++) {
            const container = document.getElementById(`phase-container-${p}`);
            if (container) {
                const dropzone = container.querySelector('.block-solution');
                if (p < state.currentSubPhase) {
                    container.style.opacity = '1';
                    container.style.pointerEvents = 'none'; // 固化锁定
                    if (dropzone) dropzone.classList.remove('active-dropzone');
                } else if (p === state.currentSubPhase) {
                    container.style.opacity = '1';
                    container.style.pointerEvents = 'auto';
                    if (dropzone) dropzone.classList.add('active-dropzone');
                } else {
                    container.style.opacity = '0.4';
                    container.style.pointerEvents = 'none';
                    if (dropzone) dropzone.classList.remove('active-dropzone');
                }
            }
        }
    }

    function renderPhasePool() {
        const pool = document.getElementById('block-pool-list');
        if (!pool || !state.preset.blocks) return;

        pool.innerHTML = '';
        state.preset.blocks.forEach(block => {
            const phase = parseInt(block.phase || 1);
            if (phase === state.currentSubPhase) {
                const el = createBlockElement(block);
                pool.appendChild(el);
            }
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
        if (!pool) return;

        if (state.poolSortable) state.poolSortable.destroy();
        const sortableOptions = {
            group: 'blocks',
            animation: 200,
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
        };

        state.poolSortable = Sortable.create(pool, { ...sortableOptions });

        for (let p = 1; p <= 3; p++) {
            const zone = document.getElementById(`solution-zone-${p}`);
            if (zone) {
                if (state[`zoneSortable${p}`]) state[`zoneSortable${p}`].destroy();
                state[`zoneSortable${p}`] = Sortable.create(zone, {
                    ...sortableOptions,
                    onAdd: function () { updateBlockPreview(); },
                    onUpdate: function () { updateBlockPreview(); },
                    onRemove: function () { updateBlockPreview(); }
                });
            }
        }
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

        // zone 1
        const z1 = document.getElementById('solution-zone-1');
        if (z1) {
            z1.querySelectorAll('.code-block').forEach(b => {
                totalBlocks++;
                preview += '    ' + '    '.repeat(parseInt(b.dataset.indent || 0)) + b.querySelector('code').textContent + '\n';
            });
        }

        preview += '    for (int i = 0; i < m; ++i) {\n';

        // zone 2
        const z2 = document.getElementById('solution-zone-2');
        if (z2) {
            z2.querySelectorAll('.code-block').forEach(b => {
                totalBlocks++;
                preview += '        ' + '    '.repeat(parseInt(b.dataset.indent || 0)) + b.querySelector('code').textContent + '\n';
            });
        }

        preview += '    }\n';

        // zone 3
        const z3 = document.getElementById('solution-zone-3');
        if (z3) {
            z3.querySelectorAll('.code-block').forEach(b => {
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
        const zone = document.getElementById(`solution-zone-${state.currentSubPhase}`);
        if (!zone) return;

        const blocks = zone.querySelectorAll('.code-block');
        if (blocks.length === 0) {
            showNotification('当前步骤区还是空的哦，请先拖入积木', 'warning');
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
        showNotification('✨ 当前步骤思维逻辑层级已对齐', 'success');
    }

    function verifyBlocks() {
        const zone = document.getElementById(`solution-zone-${state.currentSubPhase}`);
        if (!zone) return;

        const blocks = zone.querySelectorAll('.code-block');
        const studentIds = Array.from(blocks).map(b => b.dataset.blockId);

        const targetBlocks = state.preset.blocks.filter(b => parseInt(b.phase || 1) === state.currentSubPhase && !b.id.startsWith('noise-'));
        const targetIds = targetBlocks.map(b => b.id);

        if (studentIds.length === 0) {
            showNotification('请先拖入当前步骤所需的思维积木块', 'warning');
            return;
        }

        const hasNoise = studentIds.some(id => id.startsWith('noise-'));
        if (hasNoise) {
            showNotification('混入了干扰思维的噪声块哦，结合上下文再思考一下', 'warning');
            return;
        }

        if (studentIds.length !== targetIds.length) {
            showNotification('操作步骤数量还不太对，思考一下是否多余或遗漏了', 'warning');
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
            showNotification('解题先后承接顺序还不太准确，试着向伴学助手发起自由对话理清逻辑', 'warning');
            return;
        }

        if (state.currentSubPhase < 3) {
            showNotification(`🎉 步骤 ${state.currentSubPhase} 解题思维正确！已锁定并下发下一层思维零件`, 'success');
            state.currentSubPhase++;
            updateSubPhaseUI();
            renderPhasePool();
            updateBlockPreview();
        } else {
            showNotification('🏆 全批次解题思维完美通关！进入费曼阶段', 'success');
            setLoading(true);
            setTimeout(() => initStage(3), 1500);
            setLoading(false);
        }
    }

    function requestStage2Hint() {
        appendCompanionMessage('我目前在拼接步骤 ' + state.currentSubPhase + ' 时遇到阻力，请引导我思考。', 'student');
        sendCompanionQueryStream('我目前在拼接步骤 ' + state.currentSubPhase + ' 时遇到阻力，请引导我思考。');
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
            typingDiv.className = 'chat-msg msg-ai';
            typingDiv.id = typingId;
            typingDiv.innerHTML = `<div class="msg-avatar"><i class="bi bi-robot"></i></div><div class="msg-bubble"><span class="typing-dots">思考引导中...</span></div>`;
            container.appendChild(typingDiv);
            container.scrollTop = container.scrollHeight;
        }

        fetchJSON('/thinking/api/companion/chat', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                messages: messages
            })
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
        });
    }

    function appendCompanionMessage(text, sender) {
        const container = document.getElementById('companion-messages');
        if (!container) return;

        const div = document.createElement('div');
        div.className = `chat-msg msg-${sender}`;
        const avatar = sender === 'ai' ? '<i class="bi bi-robot"></i>' : '<i class="bi bi-person-fill"></i>';
        div.innerHTML = `
            <div class="msg-avatar">${avatar}</div>
            <div class="msg-bubble">${escapeHtml(text)}</div>
        `;
        container.appendChild(div);
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

        // Add initial teacher greeting
        addChatMessage('teacher', 'assistant',
            '你好！你已经完成了积木编程挑战，说明你对这道题有了不错的理解。现在我们来做一个更有趣的练习——你需要把你学到的东西教给你的同学小明（他刚开始学编程）。准备好了吗？');

        // Add initial student greeting
        addChatMessage('student', 'assistant',
            '嗨！听说你这道题做得很好，老师让你教教我😅 我刚开始学编程，你能给我讲讲这道题要怎么做吗？');
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
            <div class="chat-bubble ${isUser ? 'user-msg' : 'ai'}">${escapeHtml(content)}</div>
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
        div.innerHTML = `<i class="bi bi-lightbulb"></i><span>${escapeHtml(hint)}</span>`;
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
        state.startTime = Date.now();
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
