# Image OCR testing playbook

- Always send base64-encoded JPEG or PNG (no SVG/BMP/HEIC).
- Every test image must have real visual features (edges, text, textures).
- Resize very large images before base64 encoding.
- For animated formats, extract only the first frame.
- Never send blank or solid-colour images; they will fail the OCR request.
