## 2025-05-15 - [QR Generation Optimization]
**Learning:** Pre-instantiating the `qrcode.QRCode` object and using direct grayscale conversion (`img.convert('L')`) significantly reduces CPU overhead compared to per-chunk instantiation and manual RGB-to-BGR channel manipulation.
**Action:** Always reuse heavy engine objects (like QR generators or ML models) across loops and prefer direct grayscale conversions for monochrome outputs to minimize memory copies and processing time.
