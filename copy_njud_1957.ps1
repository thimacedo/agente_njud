# Copiar MP3s NJUD 1957
$srcDir = "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/boletins/09 - SET - 26/14 09 - SEG/"
$destDir = "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/tmp/njud_1957_workspace/"
Get-ChildItem -Path $srcDir -Filter "*NJUD_1957.mp3" | ForEach-Object {
    $dest = Join-Path $destDir $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force -ErrorAction Stop
    Write-Output ("OK: " + $_.Name)
}
