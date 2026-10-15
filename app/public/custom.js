(function() {
    // --- Polyfill for Clipboard API in insecure contexts (HTTP) ---
    if (typeof window.ClipboardItem === 'undefined') {
        window.ClipboardItem = class ClipboardItem {
            constructor(data) {
                this.data = data;
            }
        };
        
        if (typeof navigator.clipboard === 'undefined') {
            navigator.clipboard = {};
        }
        
        navigator.clipboard.write = async function(items) {
            for (const item of items) {
                for (const type in item.data) {
                    if (type === 'text/plain') {
                        let text = "";
                        const data = item.data[type];
                        if (data instanceof Blob) {
                            text = await data.text();
                        } else {
                            text = data;
                        }
                        fallbackCopyTextToClipboard(text);
                        return;
                    }
                }
            }
        };

        if (typeof navigator.clipboard.writeText === 'undefined') {
            navigator.clipboard.writeText = async function(text) {
                fallbackCopyTextToClipboard(text);
            };
        }
    }

    function fallbackCopyTextToClipboard(text) {
        var textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
        } catch (err) {
            console.error('Fallback: Oops, unable to copy', err);
        }
        document.body.removeChild(textArea);
    }
    // --- End Polyfill ---
    function init() {
        function addLoginTitle() {
            const elements = document.querySelectorAll('h5, h4, h3, h2, h1, p, span, div');
            let loginHeader = null;
            for (const el of elements) {
                if (el.textContent.trim() === 'Login to access the app' || el.textContent.trim() === 'Iniciar sesión para acceder a la aplicación') {
                    if (window.getComputedStyle(el).display !== 'none') {
                        loginHeader = el;
                        break;
                    }
                }
            }

            if (loginHeader && !document.getElementById('custom-his-title')) {
                const title = document.createElement('h1');
                title.id = 'custom-his-title';
                title.textContent = 'HIS Reportes';
                title.style.fontSize = '2.5rem';
                title.style.fontWeight = '700';
                title.style.color = '';
                title.style.marginBottom = '15px';
                title.style.textAlign = 'center';
                title.style.fontFamily = 'inherit';
                loginHeader.parentNode.insertBefore(title, loginHeader);
            }
        }

        const observer = new MutationObserver((mutations) => {
            addLoginTitle();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        setTimeout(addLoginTitle, 500);

        // --- Custom Chat Buttons Logic ---
        let isExcelActive = false;
        let isVizActive = false;

        function createCustomButtons() {
            const chatInput = document.getElementById('chat-input');
            if (!chatInput) return;

            if (document.getElementById('his-btn-excel')) return;

            // Create Excel Button
            const btnExcel = document.createElement('button');
            btnExcel.id = 'his-btn-excel';
            btnExcel.className = 'his-custom-btn';
            btnExcel.title = 'Exportar a Excel';
            btnExcel.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm1 2v3h4V5H5zm6 0v3h4V5h-4zm6 0v3h4V5h-4zM5 10v4h4v-4H5zm6 0v4h4v-4h-4zm6 0v4h4v-4h-4zM5 16v3h4v-3H5zm6 0v3h4v-3h-4zm6 0v3h4v-3h-4z"/></svg>';
            
            btnExcel.addEventListener('click', (e) => {
                e.preventDefault();
                isExcelActive = !isExcelActive;
                btnExcel.classList.toggle('active', isExcelActive);
            });

            // Create Viz Button
            const btnViz = document.createElement('button');
            btnViz.id = 'his-btn-viz';
            btnViz.className = 'his-custom-btn';
            btnViz.title = 'Generar Visualización';
            btnViz.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 3h2v18H3V3zm6 8h2v10H9V11zm6-5h2v15h-2V6zm6 4h2v11h-2V10z"/></svg>';
            
            btnViz.addEventListener('click', (e) => {
                e.preventDefault();
                isVizActive = !isVizActive;
                btnViz.classList.toggle('active', isVizActive);
            });

            const sendBtn = document.getElementById('chat-submit');
            let inputContainer = null;
            if (chatInput) {
                 inputContainer = chatInput.parentElement;
                 while (inputContainer && !inputContainer.classList.contains('flex')) {
                     inputContainer = inputContainer.parentElement;
                 }
                 if (!inputContainer) inputContainer = chatInput.parentElement;
            }
            
            const btnWrapper = document.createElement('div');
            btnWrapper.style.display = 'flex';
            btnWrapper.style.alignItems = 'center';
            btnWrapper.style.gap = '8px';
            btnWrapper.style.marginLeft = '8px';
            btnWrapper.style.marginRight = '8px';
            btnWrapper.appendChild(btnExcel);
            btnWrapper.appendChild(btnViz);

            // Intentamos encontrar el botón del clip (upload)
            const uploadBtn = document.querySelector('button[id*="upload"], button[id*="attach"]');

            if (uploadBtn) {
                uploadBtn.parentElement.insertBefore(btnWrapper, uploadBtn.nextSibling);
            } else if (sendBtn) {
                // Si no hay botón de attach (spontaneous_file_upload=false),
                // los botones se insertan justo antes del botón de enviar
                sendBtn.parentElement.insertBefore(btnWrapper, sendBtn);
            } else if (inputContainer) {
                inputContainer.appendChild(btnWrapper);
            }

            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    appendFlags(chatInput);
                }
            }, true);

            if (sendBtn) {
                sendBtn.addEventListener('click', (e) => {
                    appendFlags(chatInput);
                }, true);
            }
            
            const sendBtnObserver = new MutationObserver(() => {
                const newSendBtn = document.getElementById('chat-submit');
                if (newSendBtn && !newSendBtn.dataset.hisIntercepted) {
                    newSendBtn.dataset.hisIntercepted = 'true';
                    newSendBtn.addEventListener('click', (e) => {
                        appendFlags(chatInput);
                    }, true);
                }
            });
            if (inputContainer) {
                 sendBtnObserver.observe(inputContainer, { childList: true, subtree: true });
            }
        }

        function appendFlags(textarea) {
            if (!textarea.value || textarea.value.trim() === '') return;
            
            let flags = "";
            if (isExcelActive) flags += " [--export-excel]";
            if (isVizActive) flags += " [--viz]";

            if (flags) {
                if (textarea.value.includes('[--export-excel]') || textarea.value.includes('[--viz]')) {
                    return;
                }

                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                nativeInputValueSetter.call(textarea, textarea.value + flags);

                const event = new Event('input', { bubbles: true });
                textarea.dispatchEvent(event);
            }
        }

        const chatObserver = new MutationObserver(() => {
            createCustomButtons();
        });
        chatObserver.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
