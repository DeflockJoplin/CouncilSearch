# Joplin City‑Council Records Scraper  
*Search the council archives for any mention of Flock Safety, ALPRs, or related license‑plate‑reading technology.*

### What this repository contains  

- **Python scraper** (`DownloadPdfs.py`) – crawls the Joplin, MO city website, downloads every council agenda, minutes, and packet PDF for the years 2023‑2025.  
- **ALPR search script** (`ALPR_search.ps1`) – runs OCR on the downloaded PDFs (optional) and creates a plain‑text file **`ALPR search.txt`** that lists every occurrence of the keywords *“Flock”*, *“ALPR”*, *“license‑plate reader”*, etc.  
- **`ALPR search.txt`** – the final searchable result file (included in the repo).  

##  Contact  

If you would like a copy of **all** the scraped PDFs, please reach out to us via email.  We will arrange a secure transfer method (encrypted archive, cloud share, or physical media).


##  Quick‑start guide (PowerShell)

> All commands are meant to be run **inside the project folder** (where `DownloadPdfs.py` lives).

###  Create and activate a virtual environment  

```powershell
# Create the venv
python -m venv venv

# Activate it (PowerShell)
.\venv\Scripts\Activate.ps1
```

### Install required Python packages
```
pip install requests beautifulsoup4 tqdm
```
### Run the scraper
```
python DownloadPdfs.py
```
Get poppler from 
```
https://github.com/oschwartz10612/poppler-windows/releases
```
 
Extract the Library\bin folder of your poppler download to C:\Poppler so that pdftotext is in C:\poppler\pdftotext.exe

The PDFs will be saved under joplin_council_pdfs\<year>\.

 ### Running the OCR / ALPR search

The OCR step is optional – you can skip it if you already have a text‑based version of the PDFs.  
    Edit ALPR_search.ps1 and set the $runOCR flag to $true (default is $false)  
    Execute the PowerShell script with an execution‑policy bypass (this allows the script to run even if your system blocks unsigned scripts):  
    ```
    powershell -ExecutionPolicy Bypass -File ".\ALPR_search.ps1"  
    ```
    When OCR finishes, reset the flag to $false (to avoid re‑running OCR on the same files) and run the script again to generate the final ALPR search.txt:  
    ```
    powershell -ExecutionPolicy Bypass -File ".\ALPR_search.ps1"  
    ```
    The resulting ALPR search.txt will be placed in the project root and contains every line that mentions the target keywords, along with the source PDF name and page number.  


End of README
