param([string]$Jsx, [string]$Names)
# $Names: comma-separated list (a bash array does not bind to [string[]] through -File)
$V = "D:\Linux\coding\taxi-bot\brand\mascot\poses\vector"
$list = $Names -split ',' | Where-Object { $_ -ne '' }
[System.IO.File]::WriteAllText("$V\batch.txt", ($list -join "`n"), (New-Object System.Text.UTF8Encoding($false)))
$code = Get-Content -Raw -Encoding UTF8 "$V\$Jsx"
(New-Object -ComObject Illustrator.Application).DoJavaScript($code)
