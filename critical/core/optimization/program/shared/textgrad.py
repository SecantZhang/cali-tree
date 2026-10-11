"""Load the pinned native backward runtime independently of comparison optimizers."""
import importlib.metadata
import os

def load_textgrad(log_dir):
    if importlib.metadata.version('textgrad') != '0.1.8':
        raise RuntimeError('This adapter requires textgrad==0.1.8')
    os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
    os.environ['TEXTGRAD_LOG_DIR'] = str(log_dir)
    import textgrad as tg
    from textgrad.autograd.string_based_ops import StringBasedFunction
    from textgrad.engine import EngineLM
    return tg, StringBasedFunction, EngineLM
