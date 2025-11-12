# neocr

OCR tool with screenshot selection using Ollama.

## Installation

Install with pipx:

```bash
pipx install .
```

Or from a local directory:

```bash
pipx install /path/to/neocr
```

## Usage

Simply run:

```bash
neocr
```

The tool will:
1. Capture your screen
2. Let you select a region with your mouse
3. Extract text from the selected region using Ollama OCR
4. Copy the extracted text to your clipboard

Press ESC to cancel the selection.

## Requirements

- Python 3.8+
- Ollama with the `qwen3-vl:8b` model (or modify the model name in the code)
- tkinter (usually included with Python)
- xclip or xsel (for clipboard on Linux)

