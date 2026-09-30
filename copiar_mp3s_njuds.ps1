# Copiar MP3s dos NJUDs de setembro para os workspaces locais
# Usado pelo pipeline NJUD: divisor_boletins → montagem_jornais.py

$base_dest = "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/tmp/"
$base_src = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/"

$jobs = @(
    @{ code = "1951"; date_dir = "03 09 - QUI"; boletins = @("B1","B2","B3","B4") },
    @{ code = "1953"; date_dir = "04 09 - SEX"; boletins = @("B1","B2","B3","B7") },
    @{ code = "1954"; date_dir = "09 09 - QUA"; boletins = @("B3","B5","B6","B7") },
    @{ code = "1957"; date_dir = "14 09 - SEG"; boletins = @("B1","B5","B6","B7") }
)

foreach ($job in $jobs) {
    $src_dir = Join-Path $base_src $job.date_dir
    $dest_dir = Join-Path $base_dest "njud_$($job.code)_workspace"
    
    Write-Host "=== NJUD $($job.code) ($($job.date_dir)) ==="
    
    if (-not (Test-Path $dest_dir)) {
        New-Item -ItemType Directory -Path $dest_dir -Force | Out-Null
    }
    
    foreach ($b in $job.boletins) {
        # Encontrar o MP3 correspondente ao boletim B<n>
        $pattern = "NJUD_$($job.code)*.mp3"
        $files = Get-ChildItem -Path $src_dir -Filter $pattern -File -ErrorAction SilentlyContinue |
                 Where-Object { $_.Name -match "^BOLETIM_RADIO_TJRN_.*B${b}_" }
        
        if ($files.Count -eq 0) {
            Write-Host "  [AVISO] B${b}: não encontrado em $src_dir"
            continue
        }
        
        foreach ($f in $files) {
            $dest = Join-Path $dest_dir $f.Name
            try {
                Copy-Item -LiteralPath $f.FullName -Destination $dest -Force -ErrorAction Stop
                Write-Host "  [OK] $($f.Name)"
            } catch {
                Write-Host "  [ERRO] $($f.Name): $_"
            }
        }
    }
}

Write-Host ""
Write-Host "=== Resumo ==="
foreach ($job in $jobs) {
    $dest_dir = Join-Path $base_dest "njud_$($job.code)_workspace"
    $count = (Get-ChildItem $dest_dir -File -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host "NJUD $($job.code): $count arquivo(s) em $dest_dir"
}
