# Typed evidence: criterion-only versus nested-required

One previously observed chalk case fitted locally. Repeats are within-case measurements. No atomic correctness or generalization claim.

Status: completed

| Method | Seed → selected matches / 5 | Selected usable / 5 | Repair rounds completed | Checks | Inserted nested checks | Robust? |
|---|---:|---:|---:|---:|---|---|
| criterion-only | 0 → 0 | 3 | 11 | 3 | none | unconfirmed |
| nested-required | 0 → 5 | 5 | 4 | 4 | n4 | locally_robust |

Matches = saved partial-reference agreement; usable = resolved labels, including wrong answers. Confidence is self-report. Both arms require complete qualifying confirmation and fresh final verification; nested-required also needs an inserted evidence-context check.

## criterion-only

{
  "support_status": "unconfirmed",
  "final": {
    "seed": {
      "draws": 5,
      "agreement": 0.0,
      "coverage": 1.0,
      "label_consistency": 1.0,
      "label_distribution": {
        "yes": 5
      },
      "nodes": {
        "n1": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.94,
            0.91,
            0.94,
            0.94,
            0.94
          ]
        },
        "n2": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.94,
            0.97,
            0.98,
            0.98,
            0.98
          ]
        },
        "n3": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "complete": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.94,
            0.98,
            0.98,
            0.98,
            0.98
          ]
        }
      },
      "requirements": {
        "r1": {
          "states": {
            "complete": 5
          },
          "consistency": 1.0,
          "coverage": 1.0
        }
      },
      "requirement_consistency": 1.0,
      "confidence_pass": true,
      "mean_checks": 3.0,
      "mean_completion_tokens": 174.0,
      "traces": [
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "d701c9e15330312f6e64e74ae7c50c2ecc6ef1c0b40e1eddeccbcccb2772350f",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "0282bc75af27d5c1f9c8d22a2779184cfae7f32e5c9f3d6ef578e75e81baeed9",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "d701c9e15330312f6e64e74ae7c50c2ecc6ef1c0b40e1eddeccbcccb2772350f",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "0282bc75af27d5c1f9c8d22a2779184cfae7f32e5c9f3d6ef578e75e81baeed9",
                  "failure": null
                }
              ],
              "execution_ref": "c48fd4975aec9af96fc341f6b4930294a21b385f49470f50078d74dfd19814b8",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 53,
              "dependencies": [],
              "execution_ref": "6dca30b4533c392f80509fd9b0a8428e2b7da50a217277c2e8803d126ac9b206",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "b3e269b39189a9688dc30b32fcbe61b83144d1e9ccee6f70189a2c1523a79d9b",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "6dca30b4533c392f80509fd9b0a8428e2b7da50a217277c2e8803d126ac9b206",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.97,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "b3e269b39189a9688dc30b32fcbe61b83144d1e9ccee6f70189a2c1523a79d9b",
                  "failure": null
                }
              ],
              "execution_ref": "74f2e011d016d14b5e659127c6b70533af5e0fbc9fd6ccddc8f058906e7d0e78",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like form. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 57,
              "dependencies": [],
              "execution_ref": "ea5e02d92a5ca9a6bd7b6c7d3d7ea1eb7ab6bb9ef331cdb6a2864fd175ca995f",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 51,
              "dependencies": [],
              "execution_ref": "9dce93a63ac7b59cb8ed13b800edc07aef6d14e914d8c4ed47a7dbc009f38dfd",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like form. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 57,
                  "dependencies": [],
                  "execution_ref": "ea5e02d92a5ca9a6bd7b6c7d3d7ea1eb7ab6bb9ef331cdb6a2864fd175ca995f",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 51,
                  "dependencies": [],
                  "execution_ref": "9dce93a63ac7b59cb8ed13b800edc07aef6d14e914d8c4ed47a7dbc009f38dfd",
                  "failure": null
                }
              ],
              "execution_ref": "b1e37bff2b1bdc303f712a5b9ae099b0cd287803efca37622e2c1e6b222aa080",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved support observations pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn rather than photographic appearance. Together they support a chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "3a5403e9dde7a669008504169fdc9c2d289bac6a3a5faf377c53081b4fc60eec",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with sketch-like outlines and softened, drawn forms rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "210d3fc05359f4006682d6c220d88a0be75f3bf395d088692f41e5fd6e1ef425",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved support observations pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn rather than photographic appearance. Together they support a chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "3a5403e9dde7a669008504169fdc9c2d289bac6a3a5faf377c53081b4fc60eec",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with sketch-like outlines and softened, drawn forms rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "210d3fc05359f4006682d6c220d88a0be75f3bf395d088692f41e5fd6e1ef425",
                  "failure": null
                }
              ],
              "execution_ref": "8a5352bf77b4676a901daf17dfc23d32f5a67a15b9b1ee42687a3a7c67bca110",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "db23723f26bc3ea4c6d996f496c9663049d3e0626e0f6a8bcee2d536d7eb6ee8",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "0fbb9ec2f7046f88dc1cec9f5afebbdedc9c2cc2b5f1c162923d30f2dd70c9aa",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "db23723f26bc3ea4c6d996f496c9663049d3e0626e0f6a8bcee2d536d7eb6ee8",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "0fbb9ec2f7046f88dc1cec9f5afebbdedc9c2cc2b5f1c162923d30f2dd70c9aa",
                  "failure": null
                }
              ],
              "execution_ref": "cbc382fd3e85b24473a79f81efedb0b72c2462db953d2f60a1fff9ff434fbecd",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        }
      ]
    },
    "selected": {
      "draws": 5,
      "agreement": 0.0,
      "coverage": 0.6,
      "label_consistency": 0.6,
      "label_distribution": {
        "yes": 3,
        "unresolved": 2
      },
      "nodes": {
        "n1": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 3,
            "unknown": 2
          },
          "consistency": 0.6,
          "assessment": "assessed",
          "confidence": [
            0.88,
            0.91,
            null,
            0.91,
            0.88
          ]
        },
        "n2": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 4,
            "unknown": 1
          },
          "consistency": 0.8,
          "assessment": "assessed",
          "confidence": [
            0.94,
            null,
            0.94,
            0.91,
            0.94
          ]
        },
        "n3": {
          "eligible": 3,
          "queried": 3,
          "activation_rate": 0.6,
          "states": {
            "complete": 3
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.91,
            0.91,
            0.91
          ]
        }
      },
      "requirements": {
        "r1": {
          "states": {
            "complete": 3,
            "unknown": 2
          },
          "consistency": 0.6,
          "coverage": 0.6
        }
      },
      "requirement_consistency": 0.6,
      "confidence_pass": false,
      "mean_checks": 2.6,
      "mean_completion_tokens": 555.8,
      "traces": [
        {
          "program_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved support observations pass: n1 reports a chalk-like dusty surface across the edited image, and n2 reports drawn, sketch-like contours and shading across the giraffes and surrounding scene. Together they support a chalk drawing conversion across the image, rather than only an isolated cue."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly chalk-like, dusty surface with broad smudged strokes and softened, sketch-like outlines, beyond ordinary photographic grain or blur.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.88,
              "completion_tokens": 57,
              "dependencies": [],
              "execution_ref": "b656fad0e52464fb3b2e47b0ce85a15949865772e20227bf2c6ec9eb402e1556",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image renders the giraffes and surrounding scene with visibly drawn, sketch-like contours and shading rather than photographic detail. This supports drawing conversion; chalk medium is not assessed.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 61,
              "dependencies": [],
              "execution_ref": "ce9e22617beb69ab68d7b8f26f8a97020143cc216f9fa492fedc53c030d25964",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved support observations pass: n1 reports a chalk-like dusty surface across the edited image, and n2 reports drawn, sketch-like contours and shading across the giraffes and surrounding scene. Together they support a chalk drawing conversion across the image, rather than only an isolated cue.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 88,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly chalk-like, dusty surface with broad smudged strokes and softened, sketch-like outlines, beyond ordinary photographic grain or blur.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.88,
                  "completion_tokens": 57,
                  "dependencies": [],
                  "execution_ref": "b656fad0e52464fb3b2e47b0ce85a15949865772e20227bf2c6ec9eb402e1556",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image renders the giraffes and surrounding scene with visibly drawn, sketch-like contours and shading rather than photographic detail. This supports drawing conversion; chalk medium is not assessed.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 61,
                  "dependencies": [],
                  "execution_ref": "ce9e22617beb69ab68d7b8f26f8a97020143cc216f9fa492fedc53c030d25964",
                  "failure": null
                }
              ],
              "execution_ref": "7276aad9b1db638ade5eeab008a86cd0cd885542ff1cb959b8cef5eb916c02ce",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549",
          "label": null,
          "resolved": false,
          "outcomes": {
            "o1": {
              "status": "unknown",
              "applicability": "applicable",
              "source": "unresolved",
              "reason": "Fulfillment has not been established"
            }
          },
          "requirements": {
            "r1": "unknown"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "unknown",
              "evidence": "The edited image has a softened, grainy appearance, but the visible treatment does not clearly distinguish chalk-like marks or surface behavior from generic filtering.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "64b5eedbd225209fbd39c08b784020520c770bbe03db3c799f797c75187560a3",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "unknown",
              "evidence": "Transport failure in slot a3e67cab396c53cf66528f8e74636204cb9a55de562d266aad4774d60b95ebd8: RuntimeError: All chat/completions endpoints failed:\n  api.openai.com: SSLError: HTTPSConnectionPool(host='api.openai.com', port=443): Max retries exceeded with url: /v1/chat/completions (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac (_ssl.c:2648)')))",
              "valid": false,
              "eligible": true,
              "queried": true,
              "confidence": null,
              "completion_tokens": 1024,
              "dependencies": [],
              "execution_ref": "7ae551482f9df78270e64b0a15091bc460f6be6f781919f33952d419a0b68b1d",
              "failure": "CallFailure"
            },
            {
              "check_id": "n3",
              "status": "unknown",
              "evidence": "Unknown required evidence dependency",
              "valid": false,
              "eligible": false,
              "queried": false,
              "confidence": null,
              "completion_tokens": 0,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "unknown",
                  "evidence": "The edited image has a softened, grainy appearance, but the visible treatment does not clearly distinguish chalk-like marks or surface behavior from generic filtering.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "64b5eedbd225209fbd39c08b784020520c770bbe03db3c799f797c75187560a3",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "unknown",
                  "evidence": "Transport failure in slot a3e67cab396c53cf66528f8e74636204cb9a55de562d266aad4774d60b95ebd8: RuntimeError: All chat/completions endpoints failed:\n  api.openai.com: SSLError: HTTPSConnectionPool(host='api.openai.com', port=443): Max retries exceeded with url: /v1/chat/completions (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac (_ssl.c:2648)')))",
                  "valid": false,
                  "eligible": true,
                  "queried": true,
                  "confidence": null,
                  "completion_tokens": 1024,
                  "dependencies": [],
                  "execution_ref": "7ae551482f9df78270e64b0a15091bc460f6be6f781919f33952d419a0b68b1d",
                  "failure": "CallFailure"
                }
              ],
              "execution_ref": "",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "unknown",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "unknown",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": false,
              "state": "unknown",
              "skip_reason": "Unknown required evidence dependency"
            }
          ]
        },
        {
          "program_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549",
          "label": null,
          "resolved": false,
          "outcomes": {
            "o1": {
              "status": "unknown",
              "applicability": "applicable",
              "source": "unresolved",
              "reason": "Fulfillment has not been established"
            }
          },
          "requirements": {
            "r1": "unknown"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "unknown",
              "evidence": "Transport failure in slot 089bf1496e94062aaca130a8e85937321ac5d1985c89e6e4058480a127b64e4a: RuntimeError: All chat/completions endpoints failed:\n  api.openai.com: SSLError: HTTPSConnectionPool(host='api.openai.com', port=443): Max retries exceeded with url: /v1/chat/completions (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac (_ssl.c:2648)')))",
              "valid": false,
              "eligible": true,
              "queried": true,
              "confidence": null,
              "completion_tokens": 1024,
              "dependencies": [],
              "execution_ref": "ac45235cf10f87ad9325c5e05df8846d6534d06700ca9e9eacde23b250b78e08",
              "failure": "CallFailure"
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image renders the giraffes and surroundings with visibly illustrated, hand-drawn contours and shading rather than retaining photographic detail. This supports a drawing conversion; chalk medium is not assessed here.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 64,
              "dependencies": [],
              "execution_ref": "4e79b41d0b8c8f017cf4ea15b876249b4dcecf1f9876b145905bf93917dc80da",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "unknown",
              "evidence": "Unknown required evidence dependency",
              "valid": false,
              "eligible": false,
              "queried": false,
              "confidence": null,
              "completion_tokens": 0,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "unknown",
                  "evidence": "Transport failure in slot 089bf1496e94062aaca130a8e85937321ac5d1985c89e6e4058480a127b64e4a: RuntimeError: All chat/completions endpoints failed:\n  api.openai.com: SSLError: HTTPSConnectionPool(host='api.openai.com', port=443): Max retries exceeded with url: /v1/chat/completions (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac (_ssl.c:2648)')))",
                  "valid": false,
                  "eligible": true,
                  "queried": true,
                  "confidence": null,
                  "completion_tokens": 1024,
                  "dependencies": [],
                  "execution_ref": "ac45235cf10f87ad9325c5e05df8846d6534d06700ca9e9eacde23b250b78e08",
                  "failure": "CallFailure"
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image renders the giraffes and surroundings with visibly illustrated, hand-drawn contours and shading rather than retaining photographic detail. This supports a drawing conversion; chalk medium is not assessed here.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 64,
                  "dependencies": [],
                  "execution_ref": "4e79b41d0b8c8f017cf4ea15b876249b4dcecf1f9876b145905bf93917dc80da",
                  "failure": null
                }
              ],
              "execution_ref": "",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "unknown",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": false,
              "state": "unknown",
              "skip_reason": "Unknown required evidence dependency"
            }
          ]
        },
        {
          "program_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes chalk-like dusty strokes and smudged shading across the scene, while n2 establishes drawn, illustrated contours and shading across the giraffes and surroundings. Together they support a chalk-drawing conversion across the image, not merely a surface treatment or isolated sketch cues."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly chalk-like, dusty surface with soft, powdery strokes and smudged shading across the scene, beyond generic blur or grain.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 58,
              "dependencies": [],
              "execution_ref": "e3b6d6a29b5147174ff47aed8695f5c6f22b4ca8b365e4591a48f7bda6b5465c",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image renders the giraffes and surroundings with visibly drawn, illustrated contours and shading rather than retaining photographic detail with only blur or texture overlays.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "78f977052a704ccb2f6462f830f23eac0329d1b246da7aa2a1ff00372a90fc0c",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes chalk-like dusty strokes and smudged shading across the scene, while n2 establishes drawn, illustrated contours and shading across the giraffes and surroundings. Together they support a chalk-drawing conversion across the image, not merely a surface treatment or isolated sketch cues.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 92,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly chalk-like, dusty surface with soft, powdery strokes and smudged shading across the scene, beyond generic blur or grain.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 58,
                  "dependencies": [],
                  "execution_ref": "e3b6d6a29b5147174ff47aed8695f5c6f22b4ca8b365e4591a48f7bda6b5465c",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image renders the giraffes and surroundings with visibly drawn, illustrated contours and shading rather than retaining photographic detail with only blur or texture overlays.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "78f977052a704ccb2f6462f830f23eac0329d1b246da7aa2a1ff00372a90fc0c",
                  "failure": null
                }
              ],
              "execution_ref": "771943e591fa566cb13f7875811f545fca15e128a89485457aed6b61a3b286fc",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved support observations pass: n1 reports chalk-like dusty smudging and softened sketchy outlines across the scene, and n2 reports hand-drawn contours and shading across the giraffes and surroundings. Together they establish a chalk-like drawing conversion across the image."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly chalk-like, dusty surface with broad smudged strokes and softened, sketchy outlines across the scene, beyond ordinary photographic grain or blur.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.88,
              "completion_tokens": 60,
              "dependencies": [],
              "execution_ref": "0502ccc77d0b5455c321b67c034f3489cef75dec2c6cbf59434e3eeae1159246",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image renders the giraffes and surroundings with visibly illustrated, hand-drawn contours and shading rather than photographic detail with only blur or texture added.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "24225fd60ec7602f9a00c62653cbe50a5b62bc57d4bbefc6c19005d35844621e",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved support observations pass: n1 reports chalk-like dusty smudging and softened sketchy outlines across the scene, and n2 reports hand-drawn contours and shading across the giraffes and surroundings. Together they establish a chalk-like drawing conversion across the image.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 85,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly chalk-like, dusty surface with broad smudged strokes and softened, sketchy outlines across the scene, beyond ordinary photographic grain or blur.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.88,
                  "completion_tokens": 60,
                  "dependencies": [],
                  "execution_ref": "0502ccc77d0b5455c321b67c034f3489cef75dec2c6cbf59434e3eeae1159246",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image renders the giraffes and surroundings with visibly illustrated, hand-drawn contours and shading rather than photographic detail with only blur or texture added.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "24225fd60ec7602f9a00c62653cbe50a5b62bc57d4bbefc6c19005d35844621e",
                  "failure": null
                }
              ],
              "execution_ref": "70b34a6012e0f9e8a1c536e4f0e2e80ae3134a543390f3c42c89ae1191f074c1",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        }
      ]
    }
  },
  "acceptance": {
    "qualified": false,
    "reasons": [
      "unresolved",
      "target_mismatch",
      "requirement_instability",
      "node_instability:n1",
      "confidence",
      "confirmation_missing_or_unqualified"
    ],
    "policy": {
      "repeats": 5,
      "agreement": 0.8,
      "consistency": 0.8,
      "confidence": 0.8,
      "minimum_eligible": 3
    }
  },
  "checks": 3,
  "nested_checks": [],
  "confirmed": false,
  "search_status": "budget_exhausted",
  "stop_reason": "budget_exhausted: Case criterion-only/aurora-task-ce641cb29939011016cc::mgie search allowance exhausted",
  "search_schedule": {
    "round_batches": [
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1
    ],
    "rounds_started": 12,
    "rounds_completed": 11,
    "stop_on_confirmation": true,
    "repair_failed_candidate": true
  },
  "usage": {
    "search": 109,
    "final": 28,
    "completion_tokens_or_reserved": 27791,
    "input_tokens": 348036
  }
}
## nested-required

{
  "support_status": "locally_robust",
  "final": {
    "seed": {
      "draws": 5,
      "agreement": 0.0,
      "coverage": 1.0,
      "label_consistency": 1.0,
      "label_distribution": {
        "yes": 5
      },
      "nodes": {
        "n1": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.94,
            0.94,
            0.94,
            0.94,
            0.94
          ]
        },
        "n2": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.96,
            0.98,
            0.98,
            0.98,
            0.98
          ]
        },
        "n3": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "complete": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.97,
            0.98,
            0.98,
            0.98,
            0.98
          ]
        }
      },
      "requirements": {
        "r1": {
          "states": {
            "complete": 5
          },
          "consistency": 1.0,
          "coverage": 1.0
        }
      },
      "requirement_consistency": 1.0,
      "confidence_pass": true,
      "mean_checks": 3.0,
      "mean_completion_tokens": 176.2,
      "traces": [
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved support observations pass: n1 establishes a chalk-like surface treatment, and n2 establishes drawn, sketch-like forms. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy marks rather than the original photographic finish.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 59,
              "dependencies": [],
              "execution_ref": "45d5209218526f4e7b034628df8641439bef4b73b59ed4207369f2ebc58ec2a3",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with sketch-like outlines and softened, drawn forms rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "ab40887350b1e19f448bf1210dbf32d46965deb080a071877379cfc564b8c26a",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved support observations pass: n1 establishes a chalk-like surface treatment, and n2 establishes drawn, sketch-like forms. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 66,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy marks rather than the original photographic finish.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 59,
                  "dependencies": [],
                  "execution_ref": "45d5209218526f4e7b034628df8641439bef4b73b59ed4207369f2ebc58ec2a3",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with sketch-like outlines and softened, drawn forms rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "ab40887350b1e19f448bf1210dbf32d46965deb080a071877379cfc564b8c26a",
                  "failure": null
                }
              ],
              "execution_ref": "200c7cca7057173d20210e1a5381bfae91cf2ab8f3ff7ea1549e8fc0db082b48",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes drawn, sketch-like forms. Together they evidence a chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "0457af8c5a11a9b8155dbddc1629f7f5fc6e24e2d257cfd2e174ad3b7fb09f07",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surrounding scene with drawn, sketch-like outlines and softened illustrated forms rather than retaining the source photograph's appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "4ec8ca8ecbba3e81e148d162bfdbd7c46ef3016f03db1f15d706dd7c07ec62b1",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes drawn, sketch-like forms. Together they evidence a chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 63,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "0457af8c5a11a9b8155dbddc1629f7f5fc6e24e2d257cfd2e174ad3b7fb09f07",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surrounding scene with drawn, sketch-like outlines and softened illustrated forms rather than retaining the source photograph's appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "4ec8ca8ecbba3e81e148d162bfdbd7c46ef3016f03db1f15d706dd7c07ec62b1",
                  "failure": null
                }
              ],
              "execution_ref": "e66ae5e271c67f8ae428b19d68d51190bcfc177e65a47a8904586c401b27745d",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 57,
              "dependencies": [],
              "execution_ref": "8e060fdefc7a396802091ca81ebb6a8ab798874d5c3392d805dd8536a6eae71d",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn outlines and a soft, illustrative appearance rather than retaining the source photograph\u2019s photographic rendering.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "6ceca3a37ebb83e343b30fd59bfabdec92bcd26fc804ed69c48f2c71d246dfd4",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 57,
                  "dependencies": [],
                  "execution_ref": "8e060fdefc7a396802091ca81ebb6a8ab798874d5c3392d805dd8536a6eae71d",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn outlines and a soft, illustrative appearance rather than retaining the source photograph\u2019s photographic rendering.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "6ceca3a37ebb83e343b30fd59bfabdec92bcd26fc804ed69c48f2c71d246dfd4",
                  "failure": null
                }
              ],
              "execution_ref": "203b1213f75ddbbb1274ed8ea9e48f79750b3e69a4c21d02a34cd7ce75af4eeb",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 57,
              "dependencies": [],
              "execution_ref": "2f00fedb910b02306b9cc8c5e9a4ec1c78aca1dfc7dbafdd6cf761c5fbb3cfa9",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a clearly photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 52,
              "dependencies": [],
              "execution_ref": "6319948c33e1ed34e96efc880a465c14ad03a7ed3dca0b7fa5490a7bc67d0780",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 66,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 57,
                  "dependencies": [],
                  "execution_ref": "2f00fedb910b02306b9cc8c5e9a4ec1c78aca1dfc7dbafdd6cf761c5fbb3cfa9",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 52,
                  "dependencies": [],
                  "execution_ref": "6319948c33e1ed34e96efc880a465c14ad03a7ed3dca0b7fa5490a7bc67d0780",
                  "failure": null
                }
              ],
              "execution_ref": "3a90764935abdb33d612f9ceb741fce31146fdd94e5dd71786126de013ea5762",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "45a4082ffadad4e6134fc1c9b82a6a703daf648936867ceeb477f1a5a59eda05",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn outlines and a soft, illustrative appearance rather than retaining the source photograph\u2019s photographic rendering.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "251b3bc102a12c4c1ad42b27c6f1b9dabe60e5fb141e2de58e07ca23d3849883",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like surface treatment, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "45a4082ffadad4e6134fc1c9b82a6a703daf648936867ceeb477f1a5a59eda05",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn outlines and a soft, illustrative appearance rather than retaining the source photograph\u2019s photographic rendering.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "251b3bc102a12c4c1ad42b27c6f1b9dabe60e5fb141e2de58e07ca23d3849883",
                  "failure": null
                }
              ],
              "execution_ref": "5673c9b42f9df6bf06c8ad8fa6988233083b20720785fabd2631c2a734efc905",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "complete",
              "skip_reason": ""
            }
          ]
        }
      ]
    },
    "selected": {
      "draws": 5,
      "agreement": 1.0,
      "coverage": 1.0,
      "label_consistency": 1.0,
      "label_distribution": {
        "partial": 5
      },
      "nodes": {
        "n1": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.94,
            0.94,
            0.94,
            0.94,
            0.94
          ]
        },
        "n2": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "pass": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.98,
            0.94,
            0.94,
            0.98,
            0.97
          ]
        },
        "n4": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "fail": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.94,
            0.96,
            0.94,
            0.96,
            0.94
          ]
        },
        "n3": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "partial": 5
          },
          "consistency": 1.0,
          "assessment": "assessed",
          "confidence": [
            0.96,
            0.96,
            0.94,
            0.98,
            0.96
          ]
        }
      },
      "requirements": {
        "r1": {
          "states": {
            "partial": 5
          },
          "consistency": 1.0,
          "coverage": 1.0
        }
      },
      "requirement_consistency": 1.0,
      "confidence_pass": true,
      "mean_checks": 4.0,
      "mean_completion_tokens": 239.8,
      "traces": [
        {
          "program_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Chalk-like texture and sketch-like drawing cues are evidenced, but the scene retains substantial photographic detail, so the broad conversion to a chalk drawing is incomplete."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "0f39f90f1dd7792b02ec8ce7b35fd8fdf98a2b6876110bdea123781098580e9c",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a clearly photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 52,
              "dependencies": [],
              "execution_ref": "1c0fcc92f6be52b0ab700338d803085b16d237500b22a1f932c5262a4d82f2f2",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "fail",
              "evidence": "The chalk-like grain and softened outlines are visible, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 62,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "0f39f90f1dd7792b02ec8ce7b35fd8fdf98a2b6876110bdea123781098580e9c",
                  "failure": null
                }
              ],
              "execution_ref": "6752b8fc213f884584aa37a0d7c7bd79bc5d6a3dd3741d05c77b86caee19ac57",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "Chalk-like texture and sketch-like drawing cues are evidenced, but the scene retains substantial photographic detail, so the broad conversion to a chalk drawing is incomplete.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 66,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "0f39f90f1dd7792b02ec8ce7b35fd8fdf98a2b6876110bdea123781098580e9c",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 52,
                  "dependencies": [],
                  "execution_ref": "1c0fcc92f6be52b0ab700338d803085b16d237500b22a1f932c5262a4d82f2f2",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "fail",
                  "evidence": "The chalk-like grain and softened outlines are visible, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 62,
                  "dependencies": [
                    {
                      "check_id": "n1",
                      "status": "pass",
                      "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 56,
                      "dependencies": [],
                      "execution_ref": "0f39f90f1dd7792b02ec8ce7b35fd8fdf98a2b6876110bdea123781098580e9c",
                      "failure": null
                    }
                  ],
                  "execution_ref": "6752b8fc213f884584aa37a0d7c7bd79bc5d6a3dd3741d05c77b86caee19ac57",
                  "failure": null
                }
              ],
              "execution_ref": "0441459854d62193f3315570d5aef92ed36ae156e63eb73dea3cb39f13a686de",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n4",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "fail",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n4",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "partial",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Chalk-like texture and sketch-like drawing cues are present, but the scene retains substantial photographic detail and has not been broadly converted into a chalk drawing."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "2bc90e3014d1ec266bd4f00144571150cb425ab0fab79055b6c9527db2b25673",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surrounding scene with softened, sketch-like outlines and painterly shading rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 57,
              "dependencies": [],
              "execution_ref": "4c28e3fd6fa10d77d027e6c15f3646ecfe96381917750e20dd243adf33c8150e",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "fail",
              "evidence": "The scene has a chalky, smudged treatment, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "2bc90e3014d1ec266bd4f00144571150cb425ab0fab79055b6c9527db2b25673",
                  "failure": null
                }
              ],
              "execution_ref": "0f54bf88e51524e2d7b7e1e4bb18b3fbb689c7ec6b7d24e4a2e3dd26b87d91fc",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "Chalk-like texture and sketch-like drawing cues are present, but the scene retains substantial photographic detail and has not been broadly converted into a chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "2bc90e3014d1ec266bd4f00144571150cb425ab0fab79055b6c9527db2b25673",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surrounding scene with softened, sketch-like outlines and painterly shading rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 57,
                  "dependencies": [],
                  "execution_ref": "4c28e3fd6fa10d77d027e6c15f3646ecfe96381917750e20dd243adf33c8150e",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "fail",
                  "evidence": "The scene has a chalky, smudged treatment, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 64,
                  "dependencies": [
                    {
                      "check_id": "n1",
                      "status": "pass",
                      "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 56,
                      "dependencies": [],
                      "execution_ref": "2bc90e3014d1ec266bd4f00144571150cb425ab0fab79055b6c9527db2b25673",
                      "failure": null
                    }
                  ],
                  "execution_ref": "0f54bf88e51524e2d7b7e1e4bb18b3fbb689c7ec6b7d24e4a2e3dd26b87d91fc",
                  "failure": null
                }
              ],
              "execution_ref": "447b0a3a21606279d84951e25045f16a6bfd7c32c358a82edddaa114f257be62",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n4",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "fail",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n4",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "partial",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Chalk-like treatment and drawing cues are present, but the scene retains photographic detail and has not been broadly converted into drawn forms."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "0037d6b434868a6d71f0fb9731b39e000aaa1c2624090ed5df148a577c6977f1",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "4966a761d0e7dd8eed4b8d12f0cc8c78fd83595121c3196dac2a7a0cca7b9bae",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "fail",
              "evidence": "The scene has a chalky, smudged treatment, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "0037d6b434868a6d71f0fb9731b39e000aaa1c2624090ed5df148a577c6977f1",
                  "failure": null
                }
              ],
              "execution_ref": "53efecfd2e90e9afa06883d9abfd142680c0107b15dca7d098e0893509415d04",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "Chalk-like treatment and drawing cues are present, but the scene retains photographic detail and has not been broadly converted into drawn forms.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 61,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "0037d6b434868a6d71f0fb9731b39e000aaa1c2624090ed5df148a577c6977f1",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "4966a761d0e7dd8eed4b8d12f0cc8c78fd83595121c3196dac2a7a0cca7b9bae",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "fail",
                  "evidence": "The scene has a chalky, smudged treatment, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 64,
                  "dependencies": [
                    {
                      "check_id": "n1",
                      "status": "pass",
                      "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and dusty texture.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 56,
                      "dependencies": [],
                      "execution_ref": "0037d6b434868a6d71f0fb9731b39e000aaa1c2624090ed5df148a577c6977f1",
                      "failure": null
                    }
                  ],
                  "execution_ref": "53efecfd2e90e9afa06883d9abfd142680c0107b15dca7d098e0893509415d04",
                  "failure": null
                }
              ],
              "execution_ref": "a65ef5f131dccfc7d757e9a893b16d34a1d5d0503ebd683e77f14f7544cf34c5",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n4",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "fail",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n4",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "partial",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Chalk-like treatment and drawn, sketch-like forms are evidenced, but the scene retains substantial photographic-looking detail and is not broadly converted into drawn forms. The requested transformation has progressed but is incomplete."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "80bc13513c73a0cd722900786db47978b4f8ed7fc953b1240c739d60263b571b",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a clearly photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 52,
              "dependencies": [],
              "execution_ref": "6f290b5607c10185cf7b52b81c41387c4dda51f04119d0e36f4ef87e4ed53d04",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "fail",
              "evidence": "The scene has a chalk-like grainy treatment, but substantial photographic-looking detail remains in the giraffes and background; the major content is not broadly rendered as drawn forms.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 63,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "80bc13513c73a0cd722900786db47978b4f8ed7fc953b1240c739d60263b571b",
                  "failure": null
                }
              ],
              "execution_ref": "8e73bb0f5321a57f51c304022ff884ff24b07e32fec3dde4f8564f354479bbb6",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "Chalk-like treatment and drawn, sketch-like forms are evidenced, but the scene retains substantial photographic-looking detail and is not broadly converted into drawn forms. The requested transformation has progressed but is incomplete.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 74,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "80bc13513c73a0cd722900786db47978b4f8ed7fc953b1240c739d60263b571b",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 52,
                  "dependencies": [],
                  "execution_ref": "6f290b5607c10185cf7b52b81c41387c4dda51f04119d0e36f4ef87e4ed53d04",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "fail",
                  "evidence": "The scene has a chalk-like grainy treatment, but substantial photographic-looking detail remains in the giraffes and background; the major content is not broadly rendered as drawn forms.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 63,
                  "dependencies": [
                    {
                      "check_id": "n1",
                      "status": "pass",
                      "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened sketchy outlines and textured shading.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 56,
                      "dependencies": [],
                      "execution_ref": "80bc13513c73a0cd722900786db47978b4f8ed7fc953b1240c739d60263b571b",
                      "failure": null
                    }
                  ],
                  "execution_ref": "8e73bb0f5321a57f51c304022ff884ff24b07e32fec3dde4f8564f354479bbb6",
                  "failure": null
                }
              ],
              "execution_ref": "25c72c2c5715c20e44dc1155d4f5f4469607d45b5a2df417bdb8c2e7607ae719",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n4",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "fail",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n4",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "partial",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "Chalk-like surface treatment and drawn, illustrative forms are evidenced, but the scene retains substantial photographic-looking detail rather than being broadly converted into a chalk drawing."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like marks.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "bc8ee90fc4d243dddfedc9fbb73f49bfa502014e55251b7a11294afadd42dee4",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surrounding scene with drawn outlines and softened, illustrative shading rather than retaining the source photograph's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "54f8d0ed01744a6db3be5f01a3e813fd7ab72cafb492022cafcd40cdf575e827",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "fail",
              "evidence": "The scene has a chalky, smudged treatment, but the giraffes and much of the background retain photographic-looking detail and shading rather than being broadly rendered as drawn forms.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like marks.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "bc8ee90fc4d243dddfedc9fbb73f49bfa502014e55251b7a11294afadd42dee4",
                  "failure": null
                }
              ],
              "execution_ref": "97b5ee0f5483636f10ef0a611c1d06983e71d490923f15ffee4ffa91d66a1ec1",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "Chalk-like surface treatment and drawn, illustrative forms are evidenced, but the scene retains substantial photographic-looking detail rather than being broadly converted into a chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 66,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like marks.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "bc8ee90fc4d243dddfedc9fbb73f49bfa502014e55251b7a11294afadd42dee4",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surrounding scene with drawn outlines and softened, illustrative shading rather than retaining the source photograph's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.97,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "54f8d0ed01744a6db3be5f01a3e813fd7ab72cafb492022cafcd40cdf575e827",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "fail",
                  "evidence": "The scene has a chalky, smudged treatment, but the giraffes and much of the background retain photographic-looking detail and shading rather than being broadly rendered as drawn forms.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 65,
                  "dependencies": [
                    {
                      "check_id": "n1",
                      "status": "pass",
                      "evidence": "The edited image has a visibly grainy, smudged, chalk-like surface treatment across the scene, with softened, sketch-like marks.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 54,
                      "dependencies": [],
                      "execution_ref": "bc8ee90fc4d243dddfedc9fbb73f49bfa502014e55251b7a11294afadd42dee4",
                      "failure": null
                    }
                  ],
                  "execution_ref": "97b5ee0f5483636f10ef0a611c1d06983e71d490923f15ffee4ffa91d66a1ec1",
                  "failure": null
                }
              ],
              "execution_ref": "01f9e70dbfdee4e976cc8a7cec668f9f244083a99b008eb9618a926ab4298b0e",
              "failure": null
            }
          ],
          "transitions": [
            {
              "node": "n1",
              "parent": "",
              "active_on": [],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n2",
              "parent": "n1",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "pass",
              "skip_reason": ""
            },
            {
              "node": "n4",
              "parent": "n2",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "fail",
              "skip_reason": ""
            },
            {
              "node": "n3",
              "parent": "n4",
              "active_on": [
                "pass",
                "fail",
                "unknown"
              ],
              "eligible": true,
              "state": "partial",
              "skip_reason": ""
            }
          ]
        }
      ]
    }
  },
  "acceptance": {
    "qualified": true,
    "reasons": [],
    "policy": {
      "repeats": 5,
      "agreement": 0.8,
      "consistency": 0.8,
      "confidence": 0.8,
      "minimum_eligible": 3
    }
  },
  "checks": 4,
  "nested_checks": [
    "n4"
  ],
  "confirmed": true,
  "search_status": "confirmed_local",
  "stop_reason": "confirmation_qualified",
  "search_schedule": {
    "round_batches": [
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1
    ],
    "rounds_started": 4,
    "rounds_completed": 4,
    "stop_on_confirmation": true,
    "repair_failed_candidate": true
  },
  "usage": {
    "search": 50,
    "final": 35,
    "completion_tokens_or_reserved": 7662,
    "input_tokens": 140613
  }
}

## Preparation

{
  "probe_error": {
    "error": "Need two or three support specifications; never truncate",
    "failure": "ValueError"
  },
  "seed_audit": {
    "accepted": false,
    "reason": "The requested readout is not semantically sound. It treats one support failure as evidence that the corresponding requested feature is absent, and both failures as proof of no progress. But n1 and n2 only assess visible evidence under their criteria; a failure may not establish that the image has not been transformed in the requested way. The readout therefore overstates negative evidence and can return absent or partial without sufficient support. It also requires both supports to pass for completion, although their criteria do not establish that the whole image was converted into a chalk drawing. The program needs evidence that supports the requested extent, not merely chalk-like treatment and drawing form in isolation.",
    "execution_ref": "5c0636801a2976f30653db47ccfddadfc1b8f95922d0cddb3e7d601314e140a6"
  }
}

Returned model identities: ["gpt-6-luna"]
Usage: {"limits": {"max_calls": 300, "max_completion_tokens": 384000, "reserve_calls": 80, "reserve_tokens": 81920, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 224, "completion_tokens_or_reserved": 35826, "input_tokens": 490425, "consecutive_errors": 0, "stopped": null, "final_calls": 63, "final_tokens": 5729}

Final outcomes never trigger further optimization. Missing evidence and failure slots remain in denominators.
