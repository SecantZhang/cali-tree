"""Shared feedback templates; byte-identical to the historical prompts."""
from pathlib import Path
TEMPLATES = Path(__file__).parents[3] / 'prompts/templates/leaf_feedback_v1'
def template(name):
    return (TEMPLATES/(name+'.txt')).read_text()
