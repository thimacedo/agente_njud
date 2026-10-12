# NJUD por voz original e receita por edição

Atualização: 11/10/2026. O operador confirmou a receita: abertura, cabeças com BG, uma passagem, notas sem trilha e encerramento. Não há etapa adicional de apresentação. Para NJUD 1969–1971 autorizou notas integrais, mesmo acima de cinco minutos.

`njud.controle_producao.preparar_voz_original_njud` prepara quatro pares a partir das vozes anteriores à mixagem BOLETIM. Recebe a proveniência dos cortes e a orientação humana. Antes de copiar, verifica hashes dos brutos, manifestos, auditorias e peças, além da igualdade das amostras com os recortes da fonte. A saída é nova e separada dos insumos. Não se trata de separação de stems de um master com música.

O manifesto registra a política NJUD vigente, quatro pares na ordem editorial, hashes, fonte de proveniência e autorização literal. As saídas continuam candidatas até conferência sonora/editorial.

Opções por edição no montador canônico:

- `passagem_entre_notas: false`: uma única passagem após a escalada; exige `autorizacao_receita.receita_literal`. O padrão anterior permanece `true`.
- `limite_duracao_s`: padrão de 300 segundos. Valores acima de 300, até 900, exigem `autorizacao_duracao` com autorização, responsável e mensagem humana. Não há corte automático para satisfazer o tempo.
- `nomenclatura_canonica: true`: MP3 com nome `NJUD_NUMERO_DD-MM-AAAA.mp3`. A versão permanece na pasta de saída e nos metadados; destinos existentes continuam bloqueados.

O BG de 20% da receita é restrito às cabeças. Notas usam somente as vozes; preserva-se respiro de 120 ms após cada corpo. Metadados registram receita, duração autorizada e ausência de passagens entre notas. Nenhuma opção constitui escuta humana ou aprovação de publicação.

Validação: testes da passagem única e igualdade das amostras dos corpos, limite padrão/exceção explícita, bloqueio de mudança de cortes, brutos sem manifesto e aprovação sem verificações. Piloto 1969 auditado antes de montar 1970 e 1971. Os três foram decodificados integralmente, medidos e verificados por hash: 339,073 s, 370,293 s e 336,093 s, respectivamente.

O registro de aprovação final mantém seus gates de escuta. Para uma futura aprovação de edição acima de cinco minutos, a orientação de duração deve ser avaliada explicitamente; não registrar aprovação sonora a partir das medições automáticas.
