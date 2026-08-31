# Example resource

`basic_adb.py` loads this directory as a MaaFramework resource bundle.

For the template locator used by the example, add the template image at:

```text
examples/resource/
└── image/
    └── login/
        └── start.png
```

The locator then refers to it as:

```python
Template("login/start.png", threshold=0.85)
```

Replace the demo OCR text, ROIs, and template with values from the target application before running the example.
