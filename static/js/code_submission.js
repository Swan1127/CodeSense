/**
 * 代码提交功能模块
 * 负责处理代码提交和状态管理
 */

// 初始化代码提交功能
function initCodeSubmission() {
    console.log("初始化代码提交功能");
    
    const form = document.getElementById('code-form');
    if (!form) {
        console.error("找不到代码提交表单");
        return;
    }
    
    // 提交前的检查和处理
    form.addEventListener('submit', function(event) {
        console.log("表单提交事件触发");
        // 暂时阻止表单提交，以便我们可以处理代码获取
        event.preventDefault();
        
        // 获取代码编辑器内容
        console.log("尝试获取代码内容...");
        let code = '';
        
        try {
            // 优先使用全局辅助函数
            if (typeof getEditorCode === 'function') {
                code = getEditorCode();
                console.log("通过getEditorCode函数获取到代码，长度:", code.length);
            }
            // 如果上面的方法没有获取到内容，尝试其他方法
            else {
                // 方法1：使用全局CodeEditor对象（推荐方式）
                if (typeof window.CodeEditor !== 'undefined' && window.CodeEditor.getValue) {
                    code = window.CodeEditor.getValue('code');
                    console.log("通过CodeEditor.getValue获取到代码，长度:", code.length);
                }
                
                // 如果上面的方法没有获取到内容，尝试方法2
                if (!code && typeof editor !== 'undefined' && editor && typeof editor.getValue === 'function') {
                    code = editor.getValue();
                    console.log("通过editor.getValue获取到代码，长度:", code.length);
                }
                
                // 方法3：直接从textarea获取
                if (!code) {
                    const textarea = document.getElementById('code') || document.querySelector('textarea[name="code"]');
                    if (textarea) {
                        code = textarea.value;
                        console.log("通过textarea直接获取到代码，长度:", code.length);
                    }
                }
                
                // 方法4：从Monaco编辑器实例获取
                if (!code && typeof window.codeEditors !== 'undefined' && window.codeEditors['code']) {
                    code = window.codeEditors['code'].getValue();
                    console.log("通过window.codeEditors获取到代码，长度:", code.length);
                }
            }
            
            // 检查代码是否为空
            if (!code || code.trim() === '') {
                console.error("未获取到代码内容");
                showSubmissionMessage("请输入代码后再提交！", "danger");
                return;
            }
            
            // 将代码内容设置回表单的textarea
            const codeTextarea = document.getElementById('code');
            if (codeTextarea) {
                console.log("将代码写回表单textarea元素");
                codeTextarea.value = code;
            } else {
                console.error("找不到code textarea元素");
                // 创建一个隐藏的textarea元素
                console.log("创建一个隐藏的textarea元素");
                const newTextarea = document.createElement('textarea');
                newTextarea.name = 'code';
                newTextarea.id = 'code';
                newTextarea.style.display = 'none';
                newTextarea.value = code;
                this.appendChild(newTextarea);
            }
            
            // 在提交前显示加载状态
            showSubmitLoadingState();
            
            // 实际提交表单
            console.log("准备提交表单...");
            setTimeout(() => {
                console.log("提交表单");
                this.submit();
            }, 100);
            
        } catch (e) {
            console.error("获取代码或提交表单时出错:", e);
            showSubmissionMessage("提交代码时出错: " + e.message, "danger");
        }
    });
    
    console.log("代码表单提交功能初始化完成");
}

// 显示提交消息
function showSubmissionMessage(message, type = 'info') {
    // 检查是否存在现有的消息容器
    let messageContainer = document.querySelector('.submission-message');
    if (!messageContainer) {
        // 创建新的消息容器
        messageContainer = document.createElement('div');
        messageContainer.className = `submission-message alert alert-${type} mt-3`;
        
        // 找到表单并在之前插入消息
        const form = document.getElementById('code-form');
        if (form) {
            form.parentNode.insertBefore(messageContainer, form);
        } else {
            // 如果找不到表单，尝试找到主内容区
            const mainContent = document.querySelector('.card-body');
            if (mainContent) {
                mainContent.insertBefore(messageContainer, mainContent.firstChild);
            } else {
                // 最后的备选：添加到body
                document.body.appendChild(messageContainer);
            }
        }
    } else {
        // 更新已存在的消息容器类型
        messageContainer.className = `submission-message alert alert-${type} mt-3`;
    }
    
    // 设置消息内容
    messageContainer.innerHTML = `
        <i class="bi ${type === 'danger' ? 'bi-exclamation-triangle' : 
                      type === 'success' ? 'bi-check-circle' : 
                      'bi-info-circle'}"></i> ${message}
    `;
    
    // 滚动到消息位置
    messageContainer.scrollIntoView({ behavior: 'smooth' });
    
    // 定时自动隐藏成功消息
    if (type === 'success') {
        setTimeout(() => {
            messageContainer.style.opacity = '0';
            setTimeout(() => {
                messageContainer.remove();
            }, 500);
        }, 5000);
    }
}

// 显示提交加载状态
function showSubmitLoadingState() {
    // 禁用提交按钮防止重复提交
    const submitButton = document.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> 正在提交...';
    }
    
    // 显示提交中的消息
    showSubmissionMessage("正在提交代码，请稍候...", "info");
}

// 恢复提交按钮状态
function resetSubmitButton() {
    const submitButton = document.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="bi bi-send"></i> 提交代码';
    }
}

// 使用API提交代码（可选，用于AJAX提交）
function submitCodeViaAPI() {
    // 获取代码内容
    const code = getEditorCode();
    if (!code || code.trim() === '') {
        showSubmissionMessage("请输入代码后再提交！", "danger");
        return false;
    }
    
    // 获取作业ID
    const assignmentIdElement = document.querySelector('input[name="assignment_id"]');
    const assignmentId = assignmentIdElement ? assignmentIdElement.value : '';
    
    if (!assignmentId) {
        showSubmissionMessage("找不到作业ID，无法提交", "danger");
        return false;
    }
    
    // 获取语言
    const languageElement = document.getElementById('language');
    const language = languageElement ? languageElement.value : 'cpp';
    
    // 显示加载状态
    showSubmitLoadingState();
    
    // 发送API请求
    fetch('/api/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            code: code,
            assignment_id: assignmentId,
            language: language
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP 错误! 状态: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("提交成功:", data);
        
        // 显示成功消息
        showSubmissionMessage(`代码提交成功! 评分: ${data.data.score}/5`, "success");
        
        // 重定向到提交详情页面
        if (data.data && data.data.submission_id) {
            setTimeout(() => {
                window.location.href = `/assignments/view_submission/${data.data.submission_id}`;
            }, 1500);
        } else {
            // 如果没有提交ID，刷新当前页面
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    })
    .catch(error => {
        console.error("提交代码时出错:", error);
        showSubmissionMessage("提交失败: " + error.message, "danger");
        resetSubmitButton();
    });
    
    return true;
}

// 在页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initCodeSubmission();
    
    // 添加快捷键支持 - Ctrl+Enter 快速提交
    document.addEventListener('keydown', function(e) {
        // 检查是否为Ctrl+Enter组合键
        if (e.ctrlKey && e.key === 'Enter') {
            const submitButton = document.querySelector('button[type="submit"]');
            if (submitButton && !submitButton.disabled) {
                e.preventDefault();
                submitButton.click();
            }
        }
    });
}); 