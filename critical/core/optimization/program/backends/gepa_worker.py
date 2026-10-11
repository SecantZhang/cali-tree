"""Historical GEPA worker script; its implementation is archived."""
import runpy
from pathlib import Path
if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).parents[1]/'legacy/backends/gepa_worker.py'),run_name='__main__')
else:
    from critical.core.optimization.program.legacy.backends.gepa_worker import run
