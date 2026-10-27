import numpy as np
import pytest
from PIL import Image,ImageDraw

from critical.vision import grounded_regions_v77 as regions
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft


def test_attribute_binding_separates_source_description_from_desired_property():
    text='Turn the red cylinder blue';d=draft(text,kind='attribute');d['checks'][0]['target']='The original red cylinder'
    p=bind_program(text,d);plan=regions.plans(p)[0]
    assert plan['source_query']=='red cylinder.' and plan['edited_query']=='cylinder.'
    assert plan['property_probes'][0]['positive']=='A photo of a blue cylinder.'
    assert plan['property_probes'][0]['family']=='color'


def test_requested_relative_geometry_is_translation_invariant():
    goal={'kind':'axis','axis':'left'}
    target_a=np.asarray([.7,.3,.9,.5]);reference_a=np.asarray([.4,.3,.6,.5])
    target_b=np.asarray([.2,.3,.4,.5]);reference_b=reference_a.copy()
    expected=regions.geometry(target_a,target_b,goal,reference_a,reference_b)
    shift=np.asarray([.03,.02,.03,.02])
    assert regions.geometry(target_a+shift,target_b+shift,goal,reference_a+shift,reference_b+shift)==pytest.approx(expected)
    assert expected['axis_source_margin']<0<expected['axis_edited_margin'] and expected['axis_goal_delta']>0


def test_size_direction_uses_relative_extent_not_raw_image_resolution():
    a=regions.relative_box([40,40,80,80],[100,100]);b=regions.relative_box([100,100,140,140],[200,200])
    result=regions.geometry(a,b,{'kind':'attribute','size_goal':{'sign':-1.,'dimension':'area'}})
    assert result['size_goal_delta']==pytest.approx(.75)
    assert regions.size_goal('Make the sphere smaller')['sign']==-1
    assert regions.size_goal('Make the sphere larger')['sign']==1


def test_expected_color_fraction_is_an_input_relative_measurement():
    red=Image.new('RGB',(32,32),(255,0,0));blue=Image.new('RGB',(32,32),(0,0,255))
    assert regions.color_fraction(red,'red')==1 and regions.color_fraction(blue,'red')==0
    assert regions.color_fraction(blue,'blue')==1
    assert not any(key.startswith(('region_red','region_blue')) for key in regions.SPECS)


def test_flat_white_is_not_a_specular_spot_and_bright_local_spots_are_measured():
    assert regions.bright_spots(Image.new('RGB',(128,128),'white'))==0
    image=Image.new('RGB',(128,128),(150,0,0));ImageDraw.Draw(image).ellipse((55,55,65,65),fill='white')
    assert regions.bright_spots(image)>0


def test_missing_and_nonfinite_region_evidence_do_not_become_negative_facts():
    assert not any(regions.predicates(None).values())
    values=regions.predicates({'region_available':False})
    assert not values['region_property_goal_delta_available']
    assert not values['region_property_goal_delta_ge_0.0']
    with pytest.raises(ValueError,match='finite'):
        regions.predicates({'size_goal_delta':float('nan')})


def test_negated_or_depth_only_requests_are_not_reinterpreted_as_image_plane_goals():
    for text in ('Do not move the bowl left of the remote','Move the bowl in front of the remote'):
        d=draft(text);d['checks'][0].update(target='the bowl',reference='the remote')
        assert regions.plans(bind_program(text,d))==[]
