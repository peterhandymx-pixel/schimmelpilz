# Local OCR

Install once on Windows with `./setup-ocr.ps1`, then restart the API with `./start-local.ps1`. Node and pnpm must be installed or available in the bundled runtime. The setup downloads pinned Tesseract.js 7.0.0 and hash-checked public German/English models. Docker installs the same runtime/models during image build; this container build has not yet been validated.

In an account-owned case, upload a PDF, PNG or JPG, choose **Text prüfen**, expand **Scans / Bilder mit lokaler OCR erkennen**, choose the page range/language and start OCR. Case files are processed locally; they are not uploaded to a recognition service. Download and compare the original, correct any errors, and explicitly save the transcription review before selecting passages for research. A confidence score is not a review or legal approval.

Limits: 12 PDF pages per run, through page 80, 12 million pixels per page, 12,000 characters per location and 120,000 per run. PDF rasterization uses 180 dpi. Encrypted PDFs, unsupported formats and resource/time limits fail without replacing saved text. One extraction runs at a time. Existing nonempty extracted text, manually entered text and reviewed text are preserved; OCR only fills empty/new locations. Unsaved editor changes disable OCR. Original bytes remain unchanged. Repeated runs record their metadata, language/model hashes and skipped locations.

Owned endpoints: `GET /api/cases/{case}/documents/{document}/ocr/status` and `POST /api/cases/{case}/documents/{document}/ocr` with `start_page`, `count`, `language` (`deu`, `eng`, `deu+eng`). Image input always uses page/count 1. Selected research snapshots retain OCR origin and run ID. Private case ZIPs include run metadata.

Validated: real synthetic image and scanned PDF-page recognition, ownership/range/failure handling, original preservation, review gate and provenance; browser upload, recognition and explicit review in the separate synthetic preview. The full backend suite passed 62 tests; six frontend tests passed. This does not establish accuracy on every scan, handwriting or complex layout.
