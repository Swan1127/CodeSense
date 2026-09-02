/**
 * Shared POST/fetch SSE consumer.
 *
 * The server sends JSON in `data:` lines.  We keep the parser here so every
 * page gets identical reconnect/error handling and can render delta events
 * without duplicating stream-reader code.
 */
(function () {
    function dispatchEvent(block, handlers) {
        if (!block) return;
        const dataLines = block.split(/\r?\n/)
            .filter(line => line.startsWith('data:'))
            .map(line => line.slice(5).trimStart());
        if (!dataLines.length) return;

        let payload;
        try {
            payload = JSON.parse(dataLines.join('\n'));
        } catch (error) {
            if (handlers.onParseError) handlers.onParseError(error, dataLines.join('\n'));
            return;
        }

        const type = payload.type;
        if (type === 'start' && handlers.onStart) handlers.onStart(payload);
        if (type === 'status' && handlers.onStatus) handlers.onStatus(payload);
        if (type === 'delta' || type === 'token' || type === 'analysis_chunk') {
            if (handlers.onDelta) handlers.onDelta(payload);
        }
        if (type === 'error' || payload.error) {
            if (handlers.onError) handlers.onError(payload);
        }
        if (type === 'done' || payload.done === true || type === 'complete') {
            if (handlers.onDone) handlers.onDone(payload);
        }
        if (handlers.onEvent) handlers.onEvent(payload);
    }

    async function consumeSSE(url, options = {}, handlers = {}) {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Accept': 'text/event-stream',
                ...(options.headers || {})
            }
        });

        if (!response.ok) {
            let message = `请求失败: HTTP ${response.status}`;
            try {
                const body = await response.json();
                message = body.message || body.error || message;
            } catch (_) {
                // Keep the HTTP status when the server did not return JSON.
            }
            throw new Error(message);
        }
        if (!response.body || !response.body.getReader) {
            throw new Error('浏览器不支持流式响应');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let lastEvent = null;

        const processBuffer = (flush = false) => {
            const blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop() || '';
            blocks.forEach(block => {
                dispatchEvent(block, {
                    ...handlers,
                    onDone: payload => {
                        lastEvent = payload;
                        if (handlers.onDone) handlers.onDone(payload);
                    }
                });
            });
            if (flush && buffer.trim()) {
                dispatchEvent(buffer, {
                    ...handlers,
                    onDone: payload => {
                        lastEvent = payload;
                        if (handlers.onDone) handlers.onDone(payload);
                    }
                });
                buffer = '';
            }
        };

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            processBuffer();
        }
        buffer += decoder.decode();
        processBuffer(true);
        return lastEvent;
    }

    window.consumeSSE = consumeSSE;
})();
