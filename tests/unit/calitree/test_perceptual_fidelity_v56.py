import numpy as np
from PIL import Image, ImageFilter

from critical.core.calibration.perceptual_fidelity_v56 import statistics, predicates


def test_fidelity_identity_and_blur_cues_do_not_depend_on_file_identity(tmp_path):
    pixels = ((np.indices((128, 128)).sum(axis=0) // 4) % 2 * 255).astype('uint8')
    source = Image.fromarray(pixels).convert('RGB')
    a, b, c = [tmp_path / name for name in ('source.png', 'renamed.png', 'blur.png')]
    source.save(a)
    source.save(b)
    source.filter(ImageFilter.GaussianBlur(3)).save(c)
    same = statistics(a, b)
    blurry = statistics(a, c)
    assert same['pixel_mean_absolute_difference'] == 0
    assert np.isclose(same['luma_structure_similarity'], 1)
    assert same['edited_sharpness_ratio'] == 1
    assert blurry['edited_sharpness_ratio'] < .5 and blurry['pixel_mean_absolute_difference'] > 0
    assert all(type(value) is bool for value in predicates(blurry).values())
