/**
 * 使用API提交代码（可选，用于AJAX提交）
 * 
 * 该函数提供了通过AJAX方式提交代码的替代方案
 * 主要功能包括：
 * - 获取代码编辑器内容
 * - 验证代码不为空
 * - 获取作业ID和语言信息
 * - 发送POST请求到后端API
 * - 处理响应并显示结果
 * - 提供重试机制
 * 
 * @returns {boolean} 提交是否成功
 */
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