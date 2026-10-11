# Historical experiment runners

`calitree_adaptive_leaf.py` retains the explicit v4 semantic, v5 counting and v6 endpoint experiments and their original
APIs. Its former path is a compatibility alias; fresh default runs select fulfillment. Use `run.calitree_fulfillment`
for current runs so importing the pipeline does not load historical optimizer implementations. Existing historical
runners/replay tools remain available for their frozen experiments.
