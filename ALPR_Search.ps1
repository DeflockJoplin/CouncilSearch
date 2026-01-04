<# ---------------------------------------------------------------
   ALPR‑only search – works whether PDFs already have a text layer
   or you need to run OCR once.
   --------------------------------------------------------------- #>

# ===================== USER SETTINGS ==============================
$RootFolder = "C:\users\ndesi\Documents\JoplinScraper\joplin_council_pdfs"   # <-- change if needed
$RunOCR     = $false   # set $true only the first time you need to OCR the PDFs
$OcrFolderName = "ocr_output"   # folder that will hold the OCR PDFs
# ------------------------------------------------------------------

# ---------- Helper – add Poppler to PATH (if not already) ----------
$poppler = "C:\poppler\bin"
if (-not ($env:Path -split ';' | Where-Object { $_ -eq $poppler })) {
    $env:Path += ";$poppler"
}

# ---------- 0️⃣ Diagnostics – make sure we see something ----------
Write-Host "`n=== DIAGNOSTICS ===`n"
$pdfsInRoot = $RootFolder | Get-ChildItem -Filter *.pdf -Recurse
Write-Host "Found $($pdfsInRoot.Count) PDF(s) inside the root folder."
$ocrFolders = Get-ChildItem -Path $RootFolder -Recurse -Directory -Filter $OcrFolderName
Write-Host "Found $($ocrFolders.Count) folder(s) named '$OcrFolderName'."
$pdfsInOcr = $ocrFolders | Get-ChildItem -Filter *.pdf
Write-Host "Found $($pdfsInOcr.Count) PDF(s) inside those folders."



# ----------  OCR (run only once) ----------
if ($RunOCR) {
    Write-Host "`n=== STEP 1 OCR all PDFs (run once) ===`n"
    foreach ($pdf in $pdfsInRoot) {
        $outDir = Join-Path $RootFolder $OcrFolderName
        if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
        $dest = Join-Path $outDir $pdf.Name
        Write-Host "OCR → $($pdf.FullName)"
        python -m ocrmypdf --skip-text --output-type pdfa "$($pdf.FullName)" "$dest"
    }
    Write-Host "`nOCR step finished. Rerun the script with `$RunOCR = $false` to continue to the search phase."
    return
}

# ---------- Convert each OCR‑PDF to plain‑text -----------------
Write-Host "`n=== STEP 2 Convert OCR PDFs to .txt ===`n"
if ($pdfsInOcr.Count -eq 0) {
    Write-Warning "No PDFs to process. Check that $RootFolder points to the correct location and that the OCR PDFs are stored in subfolders named '$OcrFolderName'."
    return
}
$txtFiles = @()
foreach ($pdf in $pdfsInOcr) {
    $txtPath = [IO.Path]::ChangeExtension($pdf.FullName, ".txt")
    # pdftotext will silently create an empty file if there is no text layer.
    # We capture the exit code to warn you.
    & pdftotext -layout -enc UTF-8 "$($pdf.FullName)" "$txtPath"
    if ((Get-Item $txtPath).Length -eq 0) {
        Write-Warning "Empty .txt generated for $($pdf.Name) the PDF probably has no searchable text."
    }
    $txtFiles += $txtPath
}
Write-Host "Created $($txtFiles.Count) .txt files."

# ---------- Regex that matches ONLY ALPR‑related terms ----------
$AlprRegex = '\b(?:flock\s*safety|flock|alpr|lpr|license[-\s]?plate(?:\s*reader)?s?)\b'

# ---------- earch each .txt and write clean results -------------
Write-Host "`n=== STEP 3 Search for ALPR terms ===`n"

# Use -Path (or -LiteralPath) so PowerShell reads the file contents.
$matches = Select-String -Path $txtFiles -Pattern $AlprRegex -CaseSensitive:$false

$outFile = Join-Path $RootFolder "alpr_matches.txt"

if ($matches.Count -eq 0) {
    # Force creation of an empty file so you know the script ran
    "" | Out-File -Encoding utf8 -FilePath $outFile -Force
    Write-Host "No ALPR terms found. Empty file created at $outFile"
}
else {
    $matches | ForEach-Object {
        # Convert the temporary .txt path back to the original PDF path for readability
        $pdfPath = $_.Path -replace '\.txt$','.pdf'
        "{0}:{1}: {2}" -f $pdfPath, $_.LineNumber, $_.Line
    } | Out-File -Encoding utf8 -FilePath $outFile -Force

    Write-Host "Found $($matches.Count) matches saved to $outFile"
}

# ---------- OPTIONAL CLEAN‑UP of temporary .txt files ------------
# Uncomment the next line if you do NOT want to keep the .txt files.
# $txtFiles | Remove-Item -Force

Write-Host "`n=== SCRIPT FINISHED ===`n"