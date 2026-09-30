# Copiar MP3s para workspace NJUD 1951
$srcdir = "I:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/09 - SET - 26/03 09 - QUI/"
$destdir = "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/tmp/njud_1951_workspace/"
$filter = "NJUD_1951*.mp3"

Get-ChildItem -Path $srcdir -Filter $filter -File | ForEach-Object {
    $name = $_.Name
    $dest = Join-Path $destdir $name
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force -ErrorAction Stop
    Write-Output "Copiado: $name"
}
