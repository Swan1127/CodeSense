/**
 * Simple Highlight - 简易代码高亮库
 * 
 * 用于在外部高亮库（如highlight.js）加载失败时提供基本的代码高亮功能
 * 支持C++、Python和Java的基本关键字
 */

// 创建全局SimpleHighlight对象
(function(window) {
    // 检查是否已存在highlight.js，如果存在则不需要我们的简易高亮
    if (typeof window.hljs !== 'undefined') {
        console.log('highlight.js已加载，跳过简易高亮库的初始化');
        window.SimpleHighlight = {
            highlightAll: function() {
                // 如果已经存在hljs，则使用它进行高亮
                if (typeof hljs !== 'undefined') {
                    hljs.highlightAll();
                }
            },
            highlightElement: function(element) {
                if (typeof hljs !== 'undefined') {
                    hljs.highlightElement(element);
                }
            }
        };
        return;
    }

    console.log('highlight.js未加载，使用简易高亮库');

    // 定义不同语言的关键字
    var keywords = {
        cpp: [
            'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do', 'double',
            'else', 'enum', 'extern', 'float', 'for', 'goto', 'if', 'int', 'long', 'register',
            'return', 'short', 'signed', 'sizeof', 'static', 'struct', 'switch', 'typedef',
            'union', 'unsigned', 'void', 'volatile', 'while', 'class', 'delete', 'friend',
            'inline', 'new', 'operator', 'overload', 'private', 'protected', 'public',
            'template', 'this', 'throw', 'try', 'catch', 'virtual', 'include', 'using',
            'namespace', 'true', 'false', 'nullptr', 'bool', 'cout', 'cin', 'endl'
        ],
        python: [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if',
            'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise',
            'return', 'try', 'while', 'with', 'yield', 'True', 'False', 'None', 'print',
            'range', 'int', 'str', 'float', 'list', 'dict', 'set', 'tuple', 'self'
        ],
        java: [
            'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
            'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
            'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
            'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new', 'package',
            'private', 'protected', 'public', 'return', 'short', 'static', 'strictfp',
            'super', 'switch', 'synchronized', 'this', 'throw', 'throws', 'transient',
            'try', 'void', 'volatile', 'while', 'true', 'false', 'null', 'String', 'System'
        ]
    };

    // HTML转义函数
    function escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // 高亮单个代码块
    function highlightElement(element) {
        var language = element.className.match(/language-(\w+)/);
        language = language ? language[1] : 'cpp';  // 默认使用C++语法

        // 获取语言关键字
        var langKeywords = keywords[language] || [];
        
        // 如果没有该语言的关键字，使用通用高亮
        if (langKeywords.length === 0) {
            if (language === 'bash' || language === 'shell') {
                // 简单处理Shell命令
                highlightShell(element);
            } else {
                // 其他未知语言使用通用高亮
                highlightGeneric(element);
            }
            return;
        }

        // 获取代码内容
        var code = element.textContent;
        
        // 转义HTML
        code = escapeHtml(code);
        
        // 使用正则表达式匹配所有关键字
        var keywordRegex = new RegExp('\\b(' + langKeywords.join('|') + ')\\b', 'g');
        code = code.replace(keywordRegex, '<span class="sh-keyword">$1</span>');
        
        // 高亮字符串（简单版本）
        code = code.replace(/(["'])(.*?)\1/g, '<span class="sh-string">$1$2$1</span>');
        
        // 高亮注释（简单版本）
        if (language === 'cpp' || language === 'java') {
            // C样式注释
            code = code.replace(/\/\/(.*)$/gm, '<span class="sh-comment">//$1</span>');
            // 多行注释暂不处理，因为需要更复杂的解析
        } else if (language === 'python') {
            // Python注释
            code = code.replace(/#(.*)$/gm, '<span class="sh-comment">#$1</span>');
        }
        
        // 高亮数字
        code = code.replace(/\b(\d+)\b/g, '<span class="sh-number">$1</span>');
        
        // 设置结果
        element.innerHTML = code;
    }
    
    // Shell命令高亮
    function highlightShell(element) {
        var code = escapeHtml(element.textContent);
        
        // 高亮命令（简化版）
        code = code.replace(/^(\S+)/gm, '<span class="sh-command">$1</span>');
        
        // 高亮选项（如-f, --help）
        code = code.replace(/\s(-\w+|--\w+)/g, ' <span class="sh-option">$1</span>');
        
        // 高亮字符串
        code = code.replace(/(["'])(.*?)\1/g, '<span class="sh-string">$1$2$1</span>');
        
        element.innerHTML = code;
    }
    
    // 通用高亮（用于未知语言）
    function highlightGeneric(element) {
        var code = escapeHtml(element.textContent);
        
        // 高亮字符串
        code = code.replace(/(["'])(.*?)\1/g, '<span class="sh-string">$1$2$1</span>');
        
        // 高亮括号和标点
        code = code.replace(/([{}()\[\]])/g, '<span class="sh-punctuation">$1</span>');
        
        element.innerHTML = code;
    }

    // 设置高亮样式
    function initStyles() {
        // 检查是否已经添加了样式
        if (document.getElementById('simple-highlight-styles')) {
            return;
        }
        
        var style = document.createElement('style');
        style.id = 'simple-highlight-styles';
        style.textContent = `
            /* Simple Highlight 样式 */
            .sh-keyword { color: #569cd6; font-weight: bold; }
            .sh-string { color: #ce9178; }
            .sh-comment { color: #6a9955; font-style: italic; }
            .sh-number { color: #b5cea8; }
            .sh-punctuation { color: #d4d4d4; }
            .sh-command { color: #569cd6; font-weight: bold; }
            .sh-option { color: #9cdcfe; }
            
            /* 当使用简易高亮时的代码块基本样式 */
            pre code:not(.hljs) {
                display: block;
                font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                color: #d4d4d4;
                background-color: #1e1e1e;
                padding: 1em;
                border-radius: 0.3em;
                overflow: auto;
                line-height: 1.5;
            }
        `;
        
        document.head.appendChild(style);
    }

    // 搜索并高亮所有代码块
    function highlightAll() {
        // 初始化样式
        initStyles();
        
        // 选择所有pre > code元素
        var codeBlocks = document.querySelectorAll('pre code');
        for (var i = 0; i < codeBlocks.length; i++) {
            var block = codeBlocks[i];
            
            // 如果该块已经被highlight.js处理过，则跳过
            if (block.classList.contains('hljs')) {
                continue;
            }
            
            // 高亮代码块
            highlightElement(block);
        }
    }

    // 导出API
    window.SimpleHighlight = {
        highlightAll: highlightAll,
        highlightElement: highlightElement
    };

    // 页面加载完成后自动运行
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(highlightAll, 1);
    } else {
        document.addEventListener('DOMContentLoaded', highlightAll);
    }

})(window); 