"""Build a straightforward question/answer export using saved jacket results."""
from html import escape, unescape
import json
from pathlib import Path
import re
import subprocess

DEST = Path('/Users/zzhang/.codex/visualizations/2026/10/06/01a11245-a1f4-7cb0-be00-f8687489a6d0')
SKILL = Path('/Users/zzhang/.codex/plugins/cache/openai-bundled/visualize/1.0.47/skills/visualize')
data = json.loads((DEST / 'calitree-sol-leaf-walkthrough-data.json').read_text())['cases'][0]
source = Path(__file__).with_name('simple_jacket_source.html').read_text()
source = source.replace('__JACKET_DATA__', json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
fragment = DEST / 'calitree-jacket-simple-source.html'
fragment.write_text(source)
output = DEST / 'calitree-jacket-simple.html'
subprocess.run(['python3', str(SKILL/'scripts/render.py'),str(fragment),str(output),'--force'],check=True)
def offline(match):
    inner = re.sub(r'<script\b[^>]*\bsrc="https://[^"\s]+"[^>]*>\s*</script>', '', unescape(match.group(1)))
    return 'data-srcdoc="' + escape(inner,quote=True) + '"'
output.write_text(re.sub(r'data-srcdoc="([^"]*)"',offline,output.read_text()))
print(json.dumps({'path':str(output),'bytes':output.stat().st_size}))
