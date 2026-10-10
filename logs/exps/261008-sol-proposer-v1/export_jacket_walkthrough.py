"""Export a self-contained, saved-data-only jacket walkthrough; no provider calls."""
import json
from html import escape, unescape
from pathlib import Path
import re
import subprocess

DEST = Path('/Users/zzhang/.codex/visualizations/2026/10/06/01a11245-a1f4-7cb0-be00-f8687489a6d0')
SKILL = Path('/Users/zzhang/.codex/plugins/cache/openai-bundled/visualize/1.0.47/skills/visualize')


def main():
    data = json.loads((DEST / 'calitree-sol-leaf-walkthrough-data.json').read_text())
    data['cases'] = data['cases'][:1]
    source = (DEST / 'calitree-sol-leaf-walkthrough.html').read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    source = re.sub(r'<script id="clw-data"[^>]*>.*?</script>',
                    lambda _: '<script id="clw-data" type="application/json">' + payload + '</script>', source, flags=re.S)
    source = source.replace("const bytes=Uint8Array.from(atob($('clw-data').textContent.trim()),c=>c.charCodeAt(0));\n      const data=JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());",
                            "const data=JSON.parse($('clw-data').textContent);")
    source = source.replace("model:'sol-proposer',stage:0", "model:'luna-proposer',stage:0")
    source = source.replace('CaliTree leaf optimization</h3>', 'Jacket case · step-by-step optimization</h3>')
    source = source.replace('<label class="form-label">Case<select class="form-select" id="clw-case"></select></label>',
                            '<label class="form-label" hidden>Case<select class="form-select" id="clw-case"></select></label>')
    source = source.replace('<div id="clw-photos"',
                            '<div id="clw-decision" aria-live="polite"></div>\n  <div id="clw-photos"')
    source = source.replace('<details id="clw-node-detail" hidden>', '<details id="clw-node-detail" open hidden>')
    source = source.replace('<details id="clw-step-detail">', '<details id="clw-step-detail" open>')
    source = source.replace('Step inputs, repair and review</summary>', 'Step inputs, outputs and decisions</summary>')
    source = source.replace('Saved three-case comparison · previously observed local fitting data · no new model calls',
                            'Source: 261008-sol-proposer-v1 · jacket case from previously observed local fitting data · embedded saved results and image previews · no network or model calls')
    source = source.replace("if(stage.type==='seed'||stage.type==='audit')ref=data.cases[state.case].seed.ref;",
                            "if(stage.type==='seed'||stage.type==='audit')ref=data.cases[state.case].seed.ref;\n        if(stage.type==='seed'||stage.type==='audit')return eForSeed(run,ref);")
    source = source.replace('function observed(id)',
                            "function eForSeed(run,ref){const e=run.evaluations[ref]||{};return e.screen?[{id:'screen',name:'Starting programme · saved screening draw',ref,value:e.screen}]:[];}\n      function observed(id)")
    source = source.replace("String(i+1)+' · '+(n.role==='requested'?'Final decision':'Evidence check')",
                            "String(i+1)+' · '+n.id+' · '+(n.role==='requested'?'Final decision':'Evidence check')")
    source = source.replace("wrap.append(button,make('div','data-value',n.question),status);",
                            "if(!data.cases[state.case].seed.nodes.some(s=>s.id===n.id))status.append(make('span','viz-badge','Added check'));wrap.append(button,make('div','data-value',n.question),status);")
    extra = (Path(__file__).with_name('jacket_decision_panel.js')).read_text()
    source = source.replace('function render(){', extra + '\n      function render(){')
    source = source.replace('renderStep(stage,c,run);renderGates(c,run);', 'renderStep(stage,c,run);renderGates(c,run);renderDecision(stage,c,run);')
    fragment = DEST / 'calitree-jacket-optimization-source.html'
    fragment.write_text(source)
    output = DEST / 'calitree-jacket-optimization.html'
    subprocess.run(['python3', str(SKILL / 'scripts/render.py'), str(fragment), str(output), '--force'], check=True)
    # This walkthrough has no icons or hover tooltips. Remove their optional CDN
    # libraries from the exported srcdoc so the file makes zero network requests.
    # Keep the renderer's sandbox, CSP and bundled local runtime unchanged.
    def offline_frame(match):
        inner = unescape(match.group(1))
        inner = re.sub(r'<script\b[^>]*\bsrc="https://[^"\s]+"[^>]*>\s*</script>', '', inner)
        return 'data-srcdoc="' + escape(inner, quote=True) + '"'
    output.write_text(re.sub(r'data-srcdoc="([^"]*)"', offline_frame, output.read_text()))
    print(json.dumps({'output': str(output), 'bytes': output.stat().st_size, 'source_bytes': fragment.stat().st_size,
                      'cases': len(data['cases']), 'rounds_per_arm': {k: len(v['rounds']) for k,v in data['cases'][0]['runs'].items()}}))


if __name__ == '__main__':
    main()
