"""Deterministic whole-frame change/fidelity cues; no target or image-ID lookup."""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, laplace, sobel

from ..decision.artifacts import digest

VERSION = 'whole-frame-fidelity-predicates-v56'
THRESHOLDS = {
    'pixel_mean_absolute_difference': (.01, .03, .06, .12, .24),
    'luma_structure_similarity': (.2, .4, .6, .8, .95),
    'luma_correlation': (.2, .4, .6, .8, .95),
    'edge_correlation': (.2, .4, .6, .8, .95),
    'edited_sharpness_ratio': (.25, .5, .8, 1.25, 2.),
    'edited_contrast_ratio': (.25, .5, .8, 1.25, 2.),
    'brightness_absolute_change': (.01, .03, .06, .12, .24),
    'saturation_absolute_change': (.01, .03, .06, .12, .24),
    'color_histogram_distance': (.02, .05, .1, .2, .4),
    'coarse_luma_difference': (.01, .03, .06, .12, .24)}
SPECS = {f'fidelity_{name}_ge_{str(t).replace(".", "p")}': f'Whole-frame {name} is at least {t}; auxiliary image evidence, not proof of task fulfillment.'
         for name, thresholds in THRESHOLDS.items() for t in thresholds}
CONTRACT_REF = digest({'version': VERSION, 'specs': SPECS, 'resize': [128, 128],
                       'semantics': 'Global change, structure, color and sharpness evidence; no task grounding or geometric registration is claimed.',
                       'prohibited': 'Raw pixels/vectors, source/case IDs, hashes, object names or coordinates as learned inputs.'})


def correlation(a, b):
    a, b = a - a.mean(), b - b.mean()
    denominator = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    return float(np.sum(a * b) / denominator) if denominator > 1e-12 else 0.


def statistics(source, edited):
    def image(path):
        with Image.open(path) as value:
            return np.asarray(value.convert('RGB').resize((128, 128), Image.Resampling.BILINEAR), dtype=np.float64) / 255
    a, b = image(source), image(edited)
    wa = np.asarray([.2126, .7152, .0722])
    x, y = a @ wa, b @ wa
    ux, uy = gaussian_filter(x, 1.5), gaussian_filter(y, 1.5)
    vx = np.maximum(gaussian_filter(x * x, 1.5) - ux * ux, 0)
    vy = np.maximum(gaussian_filter(y * y, 1.5) - uy * uy, 0)
    covariance = gaussian_filter(x * y, 1.5) - ux * uy
    structure = ((2 * ux * uy + .01 ** 2) * (2 * covariance + .03 ** 2)) / ((ux * ux + uy * uy + .01 ** 2) * (vx + vy + .03 ** 2))
    edges_x = np.hypot(sobel(x, axis=0), sobel(x, axis=1))
    edges_y = np.hypot(sobel(y, axis=0), sobel(y, axis=1))
    saturation_a = np.divide(a.max(axis=2) - a.min(axis=2), a.max(axis=2), out=np.zeros_like(x), where=a.max(axis=2) > 0)
    saturation_b = np.divide(b.max(axis=2) - b.min(axis=2), b.max(axis=2), out=np.zeros_like(y), where=b.max(axis=2) > 0)
    distances = []
    for channel in range(3):
        ha = np.histogram(a[:, :, channel], bins=16, range=(0, 1))[0] / x.size
        hb = np.histogram(b[:, :, channel], bins=16, range=(0, 1))[0] / y.size
        distances.append(.5 * float(np.abs(ha - hb).sum()))
    coarse_a = x.reshape(16, 8, 16, 8).mean(axis=(1, 3))
    coarse_b = y.reshape(16, 8, 16, 8).mean(axis=(1, 3))
    return {'pixel_mean_absolute_difference': float(np.abs(a - b).mean()),
            'luma_structure_similarity': float(np.clip(structure.mean(), -1, 1)),
            'luma_correlation': correlation(x, y), 'edge_correlation': correlation(edges_x, edges_y),
            'edited_sharpness_ratio': float(np.clip((laplace(y).var() + 1e-8) / (laplace(x).var() + 1e-8), 0, 10)),
            'edited_contrast_ratio': float(np.clip((y.std() + 1e-8) / (x.std() + 1e-8), 0, 10)),
            'brightness_absolute_change': float(abs(x.mean() - y.mean())),
            'saturation_absolute_change': float(abs(saturation_a.mean() - saturation_b.mean())),
            'color_histogram_distance': float(np.mean(distances)),
            'coarse_luma_difference': float(np.abs(coarse_a - coarse_b).mean())}


def predicates(values):
    if set(values) != set(THRESHOLDS) or not all(np.isfinite(value) for value in values.values()):
        raise ValueError('Finite declared image measurements required')
    return {f'fidelity_{name}_ge_{str(t).replace(".", "p")}': bool(values[name] >= t)
            for name, thresholds in THRESHOLDS.items() for t in thresholds}
