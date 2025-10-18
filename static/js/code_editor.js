/**
 * 代码编辑器功能模块
 * 负责初始化和管理代码编辑器
 */

// 初始化代码编辑器功能
function initCodeEditorHelper() {
    const codeElement = document.getElementById('code');
    
    // 确保代码区域存在
    if (!codeElement) {
        console.error('代码编辑区域未找到');
        return;
    }
    
    // 设置基本样式
    codeElement.style.width = '100%';
    codeElement.style.minHeight = '300px';
    codeElement.style.fontFamily = 'monospace';
    codeElement.style.padding = '10px';
    codeElement.style.borderRadius = '4px';
    codeElement.style.border = '1px solid #ccc';
    codeElement.style.resize = 'vertical';
    
    // 支持Tab键缩进
    codeElement.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            
            // 获取光标位置
            const start = this.selectionStart;
            const end = this.selectionEnd;
            
            // 在光标位置插入tab
            this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
            
            // 将光标移动到插入tab后的位置
            this.selectionStart = this.selectionEnd = start + 4;
        }
    });
    
    console.log('代码编辑器辅助功能初始化完成');
    
    // 返回编辑器对象以便其他模块使用
    return {
        element: codeElement,
        
        // 获取编辑器代码内容
        getCode: function() {
            // 尝试不同的编辑器API来获取代码内容
            let code = '';
            
            try {
                // 方法1：使用全局CodeEditor对象
                if (typeof window.CodeEditor !== 'undefined' && window.CodeEditor.getValue) {
                    code = window.CodeEditor.getValue('code');
                    console.log("通过CodeEditor.getValue获取到代码，长度:", code.length);
                    return code;
                }
                
                // 方法2：使用editor全局变量
                if (!code && typeof editor !== 'undefined' && editor && typeof editor.getValue === 'function') {
                    code = editor.getValue();
                    console.log("通过editor.getValue获取到代码，长度:", code.length);
                    return code;
                }
                
                // 方法3：直接从textarea获取
                if (!code) {
                    const textarea = document.getElementById('code') || document.querySelector('textarea[name="code"]');
                    if (textarea) {
                        code = textarea.value;
                        console.log("通过textarea直接获取到代码，长度:", code.length);
                        return code;
                    }
                }
                
                // 方法4：从Monaco编辑器实例获取
                if (!code && typeof window.codeEditors !== 'undefined' && window.codeEditors['code']) {
                    code = window.codeEditors['code'].getValue();
                    console.log("通过window.codeEditors获取到代码，长度:", code.length);
                    return code;
                }
                
                // 如果以上方法都失败，返回空字符串
                console.warn("无法通过任何已知方法获取代码内容");
                return '';
            } catch (e) {
                console.error("获取代码时出错:", e);
                return '';
            }
        },
        
        // 设置编辑器代码内容
        setCode: function(code) {
            try {
                // 方法1：使用全局CodeEditor对象
                if (typeof window.CodeEditor !== 'undefined' && window.CodeEditor.setValue) {
                    window.CodeEditor.setValue('code', code);
                    return true;
                }
                
                // 方法2：使用editor全局变量
                if (typeof editor !== 'undefined' && editor && typeof editor.setValue === 'function') {
                    editor.setValue(code);
                    return true;
                }
                
                // 方法3：直接设置textarea值
                const textarea = document.getElementById('code') || document.querySelector('textarea[name="code"]');
                if (textarea) {
                    textarea.value = code;
                    return true;
                }
                
                // 方法4：使用Monaco编辑器
                if (typeof window.codeEditors !== 'undefined' && window.codeEditors['code']) {
                    window.codeEditors['code'].setValue(code);
                    return true;
                }
                
                return false;
            } catch (e) {
                console.error("设置代码内容时出错:", e);
                return false;
            }
        }
    };
}

// 在页面加载完成后初始化编辑器
document.addEventListener('DOMContentLoaded', function() {
    // 全局变量，可供其他模块使用
    window.codeEditorInstance = initCodeEditorHelper();
    
    // 设置编辑器内容变化监听
    setupEditorChangeListener();
});

// 设置编辑器内容变化监听
function setupEditorChangeListener() {
    try {
        // 尝试使用不同的编辑器API来添加变化监听
        if (typeof window.CodeEditor !== 'undefined' && window.codeEditors && window.codeEditors['code']) {
            // Monaco编辑器的监听方式
            const monacoEditor = window.codeEditors['code'];
            monacoEditor.onDidChangeModelContent(() => {
                if (typeof debouncedUpdateGuidance === 'function') {
                    debouncedUpdateGuidance();
                }
            });
            console.log("已为Monaco编辑器添加内容变化监听");
        } else if (typeof editor !== 'undefined' && typeof editor.on === 'function') {
            // CodeMirror编辑器的监听方式
            editor.on('change', () => {
                if (typeof debouncedUpdateGuidance === 'function') {
                    debouncedUpdateGuidance();
                }
            });
            console.log("已为CodeMirror编辑器添加内容变化监听");
        } else {
            // 如果都不可用，则使用textarea的input事件
            const textarea = document.getElementById('code') || document.querySelector('textarea[name="code"]');
            if (textarea) {
                textarea.addEventListener('input', function() {
                    if (typeof debouncedUpdateGuidance === 'function') {
                        debouncedUpdateGuidance();
                    }
                });
                console.log("已为textarea添加内容变化监听");
            } else {
                console.warn("未找到可监听的编辑器元素");
            }
        }
    } catch (e) {
        console.error("设置编辑器监听失败:", e);
    }
}

// 获取编辑器代码内容的全局辅助函数
function getEditorCode() {
    if (window.codeEditorInstance) {
        return window.codeEditorInstance.getCode();
    }
    
    // 如果全局实例不可用，尝试直接获取
    const codeElement = document.getElementById('code');
    return codeElement ? codeElement.value : '';
} 