# ============================================================
# PRODUZIR NJUDs — JULHO e AGOSTO 2026
# Workspace: H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026
# ============================================================

$base = "H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026"
$src  = Join-Path $base "01_BOLETINS_DIARIOS\03_AUDIOS_RADIO"
$dst  = Join-Path $base "02_JORNAIS_NJUD\03_AUDIOS_RADIO"
$log  = "$env:TEMP\njuds_jul_ago_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

"=== INÍCIO $(Get-Date) ===" | Tee-Object -FilePath $log

# ---------- funções ----------
function Get-BoletimFiles($pasta) {
    # devolve array com os arquivos mp3/wav do diretório (não recursivo)
    Get-ChildItem -Path $pasta -File |
        Where-Object { $_.Extension -match '\.(mp3|wav|m4a|ogg)$' } |
        Sort-Object Name
}

function Test-4Boletimas($pasta) {
    (Get-BoletimFiles $pasta).Count -eq 4
}

function Move-ParaNJUD($srcPasta, $dstPasta, $nudPrefix, $dataLabel, $logFile) {
    # cria pasta destino se não existir
    if (-not (Test-Path $dstPasta)) {
        New-Item -Path $dstPasta -ItemType Directory -Force | Out-Null
        "$dstPasta criado" | Tee-Object -FilePath $logFile -Append
    }

    $bols = Get-BoletimFiles $srcPasta
    if ($bols.Count -ne 4) {
        "AVISO: $srcPasta tem $($bols.Count) boletins (esperado 4) — pulando" |
            Tee-Object -FilePath $logFile -Append
        return $false
    }

    foreach ($b in $bols) {
        $novoNome = "${nudPrefix}_${dataLabel}_$($b.Name)"
        $dstFile  = Join-Path $dstPasta $novoNome
        # evita sobrescrever
        if (Test-Path $dstFile) {
            "JÁ EXISTE: $dstFile — pulando" | Tee-Object -FilePath $logFile -Append
            continue
        }
        Move-Item -Path $b.FullName -Destination $dstFile -Force
        "  MOVido: $($b.Name) → $novoNome" | Tee-Object -FilePath $logFile -Append
    }
    $true
}

function ProcessarMes($mesCod, $mesLabel, $njudInicio, $diasUteis, $logFile) {
    $srcMonth = Join-Path $src "$($mesCod) - $(Get-MesLabel $mesCod) - 26"
    $dstMonth = Join-Path $dst "$($mesCod) - $(Get-MesLabel $mesCod) - 26"

    if (-not (Test-Path $srcMonth)) {
        "ERRO: pasta fonte não encontrada: $srcMonth" | Tee-Object -FilePath $logFile -Append
        return
    }

    "--- Processando $mesLabel ($($diasUteis.Count) dias) ---" |
        Tee-Object -FilePath $logFile -Append

    $njudAtual = $njudInicio
    $ok = 0; $falha = 0; $jaExiste = 0

    foreach ($dia in $diasUteis) {
        $pastaDia = Join-Path $srcMonth "$dia - $mesCod"
        $nudPrefix = "NJUD_$njudAtual"
        $dataLabel = "$($dia.ToString('00'))-$($mesCod.ToUpper())-2026"

        $dstPasta = $dstMonth
        $sucesso = Move-ParaNJUD $pastaDia $dstPasta $nudPrefix $dataLabel $logFile

        if ($sucesso) { $ok++; $njudAtual++ }
        else         { $falha++ }

        # "limpar" pasta fonte após uso (opcional — comente se quiser manter)
        if ($sucesso) {
            Remove-Item $pastaDia -Recurse -Force -ErrorAction SilentlyContinue
            "  pasta fonte removida: $pastaDia" | Tee-Object -FilePath $logFile -Append
        }
    }

    "  OK: $ok | Falha: $falha | Nova numeração: $njudAtual" |
        Tee-Object -FilePath $logFile -Append
}

function Get-MesLabel($cod) {
    switch ($cod) {
        '01' { 'JAN' }
        '02' { 'FEV' }
        '03' { 'MAR' }
        '04' { 'ABR' }
        '05' { 'MAI' }
        '06' { 'JUN' }
        '07' { 'JUL' }
        '08' { 'AGO' }
        default { $cod }
    }
}

# ---------- dias úteis ----------
# Julho 2026 (23 dias úteis)
$julhoDias = @(
    [DateTime]'2026-07-01', [DateTime]'2026-07-02', [DateTime]'2026-07-03',
    [DateTime]'2026-07-06', [DateTime]'2026-07-07', [DateTime]'2026-07-08', [DateTime]'2026-07-09', [DateTime]'2026-07-10',
    [DateTime]'2026-07-13', [DateTime]'2026-07-14', [DateTime]'2026-07-15', [DateTime]'2026-07-16', [DateTime]'2026-07-17',
    [DateTime]'2026-07-20', [DateTime]'2026-07-21', [DateTime]'2026-07-22', [DateTime]'2026-07-23', [DateTime]'2026-07-24',
    [DateTime]'2026-07-27', [DateTime]'2026-07-28', [DateTime]'2026-07-29', [DateTime]'2026-07-30', [DateTime]'2026-07-31'
)

# Agosto 2026 (21 dias úteis)
$agostoDias = @(
    [DateTime]'2026-08-03', [DateTime]'2026-08-04', [DateTime]'2026-08-05', [DateTime]'2026-08-06', [DateTime]'2026-08-07',
    [DateTime]'2026-08-10', [DateTime]'2026-08-11', [DateTime]'2026-08-12', [DateTime]'2026-08-13', [DateTime]'2026-08-14',
    [DateTime]'2026-08-17', [DateTime]'2026-08-18', [DateTime]'2026-08-19', [DateTime]'2026-08-20', [DateTime]'2026-08-21',
    [DateTime]'2026-08-24', [DateTime]'2026-08-25', [DateTime]'2026-08-26', [DateTime]'2026-08-27', [DateTime]'2026-08-28',
    [DateTime]'2026-08-31'
)

# ---------- execução ----------
"Base: $base" | Tee-Object -FilePath $log
"Src : $src"  | Tee-Object -FilePath $log -Append
"Dst : $dst"  | Tee-Object -FilePath $log -Append

# JULHO — começa em 1905
ProcessarMes '07' 'JULHO' 1905 $julhoDias $log

# AGOSTO — começa em 1929
ProcessarMes '08' 'AGOSTO' 1929 $agostoDias $log

"`n=== FIM $(Get-Date) ===" | Tee-Object -FilePath $log
"`nLog salvo em: $log"              | Tee-Object -FilePath $log