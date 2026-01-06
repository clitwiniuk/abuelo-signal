import markdown
import os

md_path = "/Users/carlos/.gemini/antigravity/brain/2ee715d2-9af2-445f-9bc8-7ec4bc8417ae/SYSTEM_ARCHITECTURE_REPORT.md"
html_path = "/Users/carlos/.gemini/antigravity/brain/2ee715d2-9af2-445f-9bc8-7ec4bc8417ae/printable_report.html"

with open(md_path, 'r') as f:
    text = f.read()

# Convert markdown to html
html_content = markdown.markdown(text, extensions=['tables'])

# HTML template with CSS for printing
template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>System Architecture Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
            color: #333;
        }
        pre {
            background-color: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow: auto;
        }
        code {
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            background-color: rgba(27, 31, 35, 0.05);
            padding: 0.2em 0.4em;
            border-radius: 3px;
        }
        h1, h2, h3 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
        
        /* Image styling for full page */
        img[alt="System Architecture Map"] {
            display: block;
            max-width: 100%;
            height: auto;
            margin-top: 20px;
            page-break-before: always; /* Force page break before image */
            max-height: 90vh; /* Attempt to fit on page */
            object-fit: contain;
        }

        @media print {
            body { max-width: 100%; padding: 20px; }
            a { text-decoration: none; color: black; }
        }
    </style>
</head>
<body>
    REPLACE_ME
</body>
</html>
"""

final_html = template.replace("REPLACE_ME", html_content)

with open(html_path, 'w') as f:
    f.write(final_html)

print(f"Generated {html_path}")
