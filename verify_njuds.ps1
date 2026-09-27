$paths = @{
    "NJUD_1950" = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/02 09 - QUA/"
    "NJUD_1951" = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/03 09 - QUI/"
    "NJUD_1953" = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/04 09 - SEX/"
    "NJUD_1954" = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/09 09 - QUA/"
    "NJUD_1957" = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/14 09 - SEG/"
}

function Test-NJUD($njud, $dir) {
    Write-Host "=== $njud em $(Split-Path $dir -Leaf) ==="
    $files = Get-ChildItem -Path $dir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $njud }
    $files | ForEach-Object { Write-Host "  $($_.Name)" }
    $count = ($files | Measure-Object).Count
    Write-Host "  TOTAL: $count arquivos"
    Write-Host ""
}

$paths.GetEnumerator() | ForEach-Object {
    Test-NJUD $_.Key $_.Value
}
