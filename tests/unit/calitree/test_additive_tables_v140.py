from types import SimpleNamespace
import numpy as np
import pytest
from scipy.special import softmax

from critical.core.calibration.additive_tables_v140 import export,AdditiveTables,content_ref


def test_every_native_pair_and_class_cell_survives_export_and_cut_equality():
    scores=np.zeros((4,4,3));scores[1,1]=[1,0,0];scores[2,1]=[0,2,0];scores[1,2]=[0,0,3];scores[2,2]=[0,4,0]
    model=SimpleNamespace(classes_=np.array([0,1,2]),link_='mlogit',intercept_=np.array([.1,.2,.3]),
        term_features_=[(0,1)],term_scores_=[scores],bins_=[[np.array([.5])],[np.array([.5])]])
    artifact=export(model,['progress','endpoint'],{'progress':'An explicit progress claim.','endpoint':'An explicit endpoint claim.'})
    p=AdditiveTables(artifact).predict_proba([[0,0],[1,0],[0,1],[.5,.5]])
    expected=softmax(np.array([[1,0,0],[0,2,0],[0,0,3],[0,4,0]])+model.intercept_,axis=1)
    assert np.allclose(p,expected,atol=1e-15,rtol=0) and len(artifact['terms'])==1


def test_rehashed_malformed_table_does_not_become_executable():
    model=SimpleNamespace(classes_=np.array([0,1,2]),link_='mlogit',intercept_=np.zeros(3),term_features_=[(0,)],term_scores_=[np.zeros((4,3))],bins_=[[np.array([.5])]])
    artifact=export(model,['flag'],{'flag':'A model flag.'});artifact['terms'][0]['scores'].pop();artifact['artifact_ref']=content_ref(artifact)
    with pytest.raises(ValueError,match='dimensions'):AdditiveTables(artifact)
