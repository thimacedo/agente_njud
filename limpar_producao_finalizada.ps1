<#
.SYNOPSIS
    Limpeza pos-producao do pipeline DIVISOR (NJUD).
    Remove (para quarentena) pastas/mp3 ja finalizados, mantendo relatorios e logs.

.DESCRIPTION
    Criterio de "finalizado": um NJUD e considerado finalizado se ja existe o mp3
    correspondente sincronizado em:
        H:\Meu Drive\RADIO TJRN CONTEUDO\00_PRODUCAO_2026\02_JORNAIS_NJUD\03_AUDIOS_RADIO\<MES>\
    (apenas pastas ativas, NAO conta _arquivo_morto como prova de entrega).

    O H:\ NUNCA e modificado por este script (somente leitura, como manda DECISOES.md).

    Alvos de limpeza (ver -Root nos parametros):
      1) DIVISOR\JORNAIS\<MES>\NJUD <numero>\        -> pasta inteira, se numero NJUD estiver finalizado
      2) DIVISOR\data\processed\...\<numero>\        -> cortes intermediarios do NJUD finalizado
      3) DIVISOR\downloads\                          -> mp3 soltos, nao pertencem ao pipeline NJUD (limpeza incondicional)
      4) DIVISOR\legacy_archive\                     -> snapshot antigo (limpeza incondicional)

    NUNCA remove: .md .csv .json .log .ps1 .py (relatorios, estado, codigo).

    Por padrao roda em modo DRY-RUN (so mostra o que faria).
    Use -Apply para mover de fato os itens para a quarentena.

.PARAMETER DivisorRoot
    Raiz do projeto local (default: E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR).

.PARAMETER DriveNjudPath
    Caminho do H: onde ficam os NJUDs sincronizados (prova de finalizacao).

.PARAMETER Apply
    Se presente, MOVE de fato os itens para a quarentena. Sem isso, so simula (dry-run).

.EXAMPLE
    # 1) Ver o que seria limpo, sem tocar em nada:
    .\limpar_producao_finalizada.ps1

.EXAMPLE
    # 2) Aplicar de verdade (move para quarentena):
    .\limpar_producao_finalizada.ps1 -Apply

.EXAMPLE
    # 3) Apontando para caminhos diferentes do padrao:
    .\limpar_producao_finalizada.ps1 -DivisorRoot "F:\Projetos\DIVISOR" -Apply
#>

param(
    [string]$DivisorRoot = "E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR",
    [string]$DriveNjudPath = "H:\Meu Drive\RADIO TJRN CONTEUDO\00_PRODUCAO_2026\02_JORNAIS_NJUD\03_AUDIOS_RADIO",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

# --- extensões que NUNCA são removidas, em nenhum alvo ---
$ExtensoesProtegidas = @(".md", ".csv", ".json", ".log", ".ps1", ".py", ".txt", ".gitignore")

$DataHoje = Get-Date -Format "yyyyMMdd_HHmmss"
$Quarentena = Join-Path $DivisorRoot "_LIXEIRA_LIMPEZA\$DataHoje"
$RelatorioPath = Join-Path $DivisorRoot "logs\limpeza_relatorio_$DataHoje.log"

function Write-Log {
    param([string]$Msg)
    Write-Host $Msg
    Add-Content -Path $RelatorioPath -Value $Msg -Encoding UTF8
}

# --- 1) Descobrir quais NJUDs (numero) já estão finalizados, por mês, olhando o H: ---
function Get-NjudsFinalizados {
    param([string]$DrivePath)

    $mapa = @{}   # mes (nome da pasta) -> HashSet de numeros NJUD finalizados

    if (-not (Test-Path $DrivePath)) {
        Write-Log "[AVISO] Caminho do Drive nao encontrado: $DrivePath — nenhum NJUD sera considerado finalizado."
        return $mapa
    }

    $pastasMes = Get-ChildItem -Path $DrivePath -Directory | Where-Object {
        $_.Name -notmatch "_arquivo_morto" -and $_.Name -notmatch "__extra"
    }

    foreach ($pastaMes in $pastasMes) {
        $numeros = New-Object System.Collections.Generic.HashSet[string]
        Get-ChildItem -Path $pastaMes.FullName -File -Filter "NJUD_*.mp3" -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object {
                if ($_.Name -match '^NJUD_(\d+)_') {
                    [void]$numeros.Add($Matches[1])
                }
            }
        $mapa[$pastaMes.Name] = $numeros
        Write-Log "[INFO] H:\...\$($pastaMes.Name) -> $($numeros.Count) NJUD(s) finalizado(s)."
    }

    return $mapa
}

# --- 2) Verifica se um caminho contém um número NJUD que está na lista de finalizados ---
function Test-NjudFinalizado {
    param(
        [string]$Caminho,
        [hashtable]$MapaFinalizados
    )
    # tenta achar "NJUD 1903", "NJUD_1903", "NJUD1903" no caminho
    if ($Caminho -notmatch 'NJUD[_ ]?(\d+)') {
        return $false
    }
    $numero = $Matches[1]
    foreach ($conjunto in $MapaFinalizados.Values) {
        if ($conjunto.Contains($numero)) { return $true }
    }
    return $false
}

# --- 3) Move um item (arquivo ou pasta) para a quarentena, preservando caminho relativo ---
function Move-ParaQuarentena {
    param(
        [string]$ItemPath,
        [string]$RaizOrigem
    )
    $relativo = $ItemPath.Substring($RaizOrigem.Length).TrimStart('\')
    $destino = Join-Path $Quarentena $relativo
    $destinoDir = Split-Path $destino -Parent

    if ($Apply) {
        New-Item -ItemType Directory -Path $destinoDir -Force | Out-Null
        Move-Item -Path $ItemPath -Destination $destino -Force
        Write-Log "[MOVIDO] $ItemPath -> $destino"
    } else {
        Write-Log "[DRY-RUN] moveria: $ItemPath -> $destino"
    }
}

# --- 4) Limpeza condicionada a NJUD finalizado (JORNAIS/ e data/processed/) ---
function Limpar-PastaCondicionalNjud {
    param([string]$PastaAlvo, [hashtable]$MapaFinalizados)

    if (-not (Test-Path $PastaAlvo)) {
        Write-Log "[SKIP] Pasta nao existe: $PastaAlvo"
        return
    }

    Write-Log "`n=== Verificando (condicionado a NJUD finalizado): $PastaAlvo ==="

    # Pastas de NJUD (ex: "NJUD 1903", subpastas por numero)
    Get-ChildItem -Path $PastaAlvo -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match 'NJUD[_ ]?\d+' } |
        ForEach-Object {
            if (Test-NjudFinalizado -Caminho $_.FullName -MapaFinalizados $MapaFinalizados) {
                Move-ParaQuarentena -ItemPath $_.FullName -RaizOrigem $DivisorRoot
            }
        }

    # mp3 soltos (fora de pastas NJUD) cujo nome do arquivo contém o numero
    Get-ChildItem -Path $PastaAlvo -File -Filter "*.mp3" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { Test-Path $_.FullName } |
        ForEach-Object {
            if (Test-NjudFinalizado -Caminho $_.FullName -MapaFinalizados $MapaFinalizados) {
                Move-ParaQuarentena -ItemPath $_.FullName -RaizOrigem $DivisorRoot
            }
        }
}

# --- 5) Limpeza incondicional (downloads/, legacy_archive/) — protegendo extensões de relatório ---
function Limpar-PastaIncondicional {
    param([string]$PastaAlvo)

    if (-not (Test-Path $PastaAlvo)) {
        Write-Log "[SKIP] Pasta nao existe: $PastaAlvo"
        return
    }

    Write-Log "`n=== Limpeza incondicional (nao ligada a NJUD): $PastaAlvo ==="

    Get-ChildItem -Path $PastaAlvo -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $ExtensoesProtegidas -notcontains $_.Extension.ToLower() } |
        ForEach-Object {
            Move-ParaQuarentena -ItemPath $_.FullName -RaizOrigem $DivisorRoot
        }
}

# ============================ EXECUÇÃO ============================

Write-Log "===================================================="
Write-Log " LIMPEZA DE PRODUCAO FINALIZADA — DIVISOR"
Write-Log " Modo: $(if ($Apply) { 'APLICANDO (move para quarentena)' } else { 'DRY-RUN (simulacao, nada e alterado)' })"
Write-Log " Raiz: $DivisorRoot"
Write-Log " Quarentena: $Quarentena"
Write-Log "===================================================="

$mapaFinalizados = Get-NjudsFinalizados -DrivePath $DriveNjudPath

Limpar-PastaCondicionalNjud -PastaAlvo (Join-Path $DivisorRoot "JORNAIS") -MapaFinalizados $mapaFinalizados
Limpar-PastaCondicionalNjud -PastaAlvo (Join-Path $DivisorRoot "data\processed") -MapaFinalizados $mapaFinalizados
Limpar-PastaIncondicional  -PastaAlvo (Join-Path $DivisorRoot "downloads")
Limpar-PastaIncondicional  -PastaAlvo (Join-Path $DivisorRoot "legacy_archive")

Write-Log "`n===================================================="
if ($Apply) {
    Write-Log " Concluido. Itens movidos para: $Quarentena"
    Write-Log " Confira antes de apagar de vez. Sugestao: manter a quarentena por"
    Write-Log " pelo menos 7-14 dias antes de fazer Remove-Item -Recurse -Force nela."
} else {
    Write-Log " Simulacao concluida. Nenhum arquivo foi alterado."
    Write-Log " Revise o relatorio acima e rode novamente com -Apply para executar de fato."
}
Write-Log " Relatorio salvo em: $RelatorioPath"
Write-Log "===================================================="
