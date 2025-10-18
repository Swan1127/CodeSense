/**
 * 浏览器兼容性补丁
 * 处理Safari和其他浏览器的特殊兼容性问题
 */

(function() {
    // 检测Safari浏览器
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    
    if (isSafari) {
        console.log('检测到Safari浏览器，应用兼容性补丁');
        
        // 处理autocapitalize问题
        document.addEventListener('DOMContentLoaded', function() {
            // 移除Safari不支持的autocapitalize属性
            const textareas = document.querySelectorAll('textarea[autocapitalize]');
            textareas.forEach(function(textarea) {
                textarea.removeAttribute('autocapitalize');
            });
            
            // 确保所有表单字段都有id和name属性
            const formFields = document.querySelectorAll('input, textarea, select');
            formFields.forEach(function(field) {
                if (!field.id && !field.name) {
                    // 生成一个唯一ID
                    const uniqueId = 'field-' + Math.random().toString(36).substring(2, 15);
                    field.id = uniqueId;
                    field.name = uniqueId;
                }
            });
        });
        
        // 修复Safari中的Monaco编辑器问题
        window.MonacoSafariCompatFix = {
            init: function() {
                // 创建一个钩子来拦截Monaco创建的TextArea元素
                const originalCreateElement = document.createElement;
                document.createElement = function(tagName) {
                    const element = originalCreateElement.call(document, tagName);
                    if (tagName.toLowerCase() === 'textarea') {
                        // 设置ID和name，但不设置autocapitalize
                        const uniqueId = 'monaco-textarea-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
                        element.id = uniqueId;
                        element.name = uniqueId;
                    }
                    return element;
                };
                
                // 记录原始方法以便恢复
                window.MonacoSafariCompatFix.originalCreateElement = originalCreateElement;
            },
            
            restore: function() {
                // 恢复原始createElement方法
                if (window.MonacoSafariCompatFix.originalCreateElement) {
                    document.createElement = window.MonacoSafariCompatFix.originalCreateElement;
                }
            }
        };
        
        // 在页面加载时应用钩子
        window.MonacoSafariCompatFix.init();
    }
})(); 