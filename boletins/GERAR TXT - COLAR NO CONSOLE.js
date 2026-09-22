(function criarInterfaceDownloadDocs() {
    // 1. Remove interface anterior se existir
    const caixaAntiga = document.getElementById("box-extrator-docs");
    if (caixaAntiga) caixaAntiga.remove();

    // 2. Cria elementos via DOM nativo
    const div = document.createElement("div");
    div.id = "box-extrator-docs";
    div.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        width: 420px;
        background: #ffffff;
        border: 2px solid #1a73e8;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        z-index: 999999;
        font-family: Arial, sans-serif;
        color: #333;
    `;

    const titulo = document.createElement("h3");
    titulo.style.cssText = "margin-top:0; font-size:16px; color:#1a73e8;";
    titulo.textContent = "📄 Unificador de Google Docs (TXT)";

    const instrucoes = document.createElement("p");
    instrucoes.style.cssText = "font-size:12px; margin-bottom:8px;";
    instrucoes.textContent = "Cole abaixo os links dos documentos (juntos ou separados):";

    const textarea = document.createElement("textarea");
    textarea.id = "txt-links-input";
    textarea.rows = 8;
    textarea.placeholder = "Cole os links aqui...";
    textarea.style.cssText = "width:100%; box-sizing:border-box; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:11px; resize:vertical;";

    const containerBotoes = document.createElement("div");
    containerBotoes.style.cssText = "margin-top:10px; display:flex; justify-content:space-between;";

    const btnCancelar = document.createElement("button");
    btnCancelar.textContent = "Cancelar";
    btnCancelar.style.cssText = "padding:8px 12px; background:#f1f3f4; border:none; border-radius:4px; cursor:pointer;";

    const btnProcessar = document.createElement("button");
    btnProcessar.textContent = "Gerar TXT Único";
    btnProcessar.style.cssText = "padding:8px 16px; background:#1a73e8; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:bold;";

    containerBotoes.appendChild(btnCancelar);
    containerBotoes.appendChild(btnProcessar);

    const statusMsg = document.createElement("div");
    statusMsg.id = "status-docs-msg";
    statusMsg.style.cssText = "margin-top:10px; font-size:12px; color:#5f6368;";

    div.appendChild(titulo);
    div.appendChild(instrucoes);
    div.appendChild(textarea);
    div.appendChild(containerBotoes);
    div.appendChild(statusMsg);

    document.body.appendChild(div);

    // 3. Ações dos botões
    btnCancelar.onclick = () => div.remove();

    btnProcessar.onclick = async () => {
        const textoComLinks = textarea.value;

        const regexDocId = /\/d\/([a-zA-Z0-9-_]+)/g;
        let match;
        const ids = [];

        while ((match = regexDocId.exec(textoComLinks)) !== null) {
            ids.push(match[1]);
        }

        if (ids.length === 0) {
            statusMsg.style.color = "#d93025";
            statusMsg.textContent = "❌ Nenhum link do Google Docs identificado.";
            return;
        }

        statusMsg.style.color = "#1a73e8";
        statusMsg.textContent = `⏳ Baixando 0 de ${ids.length} documentos...`;

        let conteudoConsolidado = "";

        for (let i = 0; i < ids.length; i++) {
            const id = ids[i];
            const exportUrl = `https://docs.google.com/document/d/${id}/export?format=txt`;

            statusMsg.textContent = `⏳ Baixando [${i + 1}/${ids.length}]...`;

            try {
                const response = await fetch(exportUrl);
                if (!response.ok) throw new Error(`Status ${response.status}`);
                const texto = await response.text();

                conteudoConsolidado += `========================================\n`;
                conteudoConsolidado += `DOCUMENTO [${i + 1}/${ids.length}] - ID: ${id}\n`;
                conteudoConsolidado += `========================================\n\n`;
                conteudoConsolidado += texto.trim() + "\n\n\n";
            } catch (erro) {
                console.error(`Erro ao baixar ID: ${id}`, erro);
                conteudoConsolidado += `[ERRO AO EXTRAIR DOCUMENTO ID: ${id}]\n\n\n`;
            }
        }

        // Fazer download do arquivo consolidado
        const blob = new Blob([conteudoConsolidado], { type: "text/plain;charset=utf-8" });
        const urlBlob = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = urlBlob;
        a.download = `boletins_unificados_${new Date().toISOString().slice(0, 10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(urlBlob);

        statusMsg.style.color = "#188038";
        statusMsg.textContent = "✅ Download concluído com sucesso!";
        setTimeout(() => div.remove(), 2500);
    };
})();