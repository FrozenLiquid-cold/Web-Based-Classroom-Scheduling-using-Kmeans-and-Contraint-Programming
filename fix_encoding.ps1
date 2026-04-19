$filePath = 'd:\Downloads\Antigrav\SchedulerUI\src\pages\Instructor\Schedule.jsx'
$lines = [System.IO.File]::ReadAllLines($filePath, [System.Text.Encoding]::UTF8)

# Fix line 82 (0-indexed 81) - replace the entire line
$lines[81] = "                // Single API call instead of multiple calls"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($filePath, $lines, $utf8NoBom)
Write-Host "Fixed line 82"
