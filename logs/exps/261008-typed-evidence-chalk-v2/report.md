# Typed evidence: criterion-only versus nested-required

One previously observed chalk case fitted locally. Repeats are within-case measurements. No atomic correctness or generalization claim.

Status: completed

| Method | Seed → selected matches / 5 | Selected usable / 5 | Checks | Inserted nested checks | Robust? |
|---|---:|---:|---:|---|---|
| criterion-only | 0 → 2 | 2 | 3 | none | unconfirmed |
| nested-required | 0 → 0 | 5 | 4 | n4 | unconfirmed |

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
            0.91,
            0.88,
            0.91,
            0.91,
            0.91
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
            0.96,
            0.96,
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
            0.98,
            0.97,
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
      "mean_completion_tokens": 171.4,
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, dusty surface and soft, smudged marks across the scene, giving it a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 56,
              "dependencies": [],
              "execution_ref": "d701c9e15330312f6e64e74ae7c50c2ecc6ef1c0b40e1eddeccbcccb2772350f",
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
              "execution_ref": "0282bc75af27d5c1f9c8d22a2779184cfae7f32e5c9f3d6ef578e75e81baeed9",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, dusty surface and soft, smudged marks across the scene, giving it a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 56,
                  "dependencies": [],
                  "execution_ref": "d701c9e15330312f6e64e74ae7c50c2ecc6ef1c0b40e1eddeccbcccb2772350f",
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
                  "execution_ref": "0282bc75af27d5c1f9c8d22a2779184cfae7f32e5c9f3d6ef578e75e81baeed9",
                  "failure": null
                }
              ],
              "execution_ref": "26071990d234885dc58ed85fdb9fc1963920f031872aa564f8bfbfd0b61e173d",
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
              "reason": "Both saved support observations pass: n1 establishes a chalk-like medium, and n2 establishes a drawing-like rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, dusty surface and soft, sketch-like marks consistent with a chalk-like treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.88,
              "completion_tokens": 50,
              "dependencies": [],
              "execution_ref": "6dca30b4533c392f80509fd9b0a8428e2b7da50a217277c2e8803d126ac9b206",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "b3e269b39189a9688dc30b32fcbe61b83144d1e9ccee6f70189a2c1523a79d9b",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved support observations pass: n1 establishes a chalk-like medium, and n2 establishes a drawing-like rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 63,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, dusty surface and soft, sketch-like marks consistent with a chalk-like treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.88,
                  "completion_tokens": 50,
                  "dependencies": [],
                  "execution_ref": "6dca30b4533c392f80509fd9b0a8428e2b7da50a217277c2e8803d126ac9b206",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "b3e269b39189a9688dc30b32fcbe61b83144d1e9ccee6f70189a2c1523a79d9b",
                  "failure": null
                }
              ],
              "execution_ref": "a855dabaabd3ed66fd4200970a5858e128a85bec21291b7dd0bec369bbb6ea4a",
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "ea5e02d92a5ca9a6bd7b6c7d3d7ea1eb7ab6bb9ef331cdb6a2864fd175ca995f",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source's photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "9dce93a63ac7b59cb8ed13b800edc07aef6d14e914d8c4ed47a7dbc009f38dfd",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "ea5e02d92a5ca9a6bd7b6c7d3d7ea1eb7ab6bb9ef331cdb6a2864fd175ca995f",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining the source's photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "9dce93a63ac7b59cb8ed13b800edc07aef6d14e914d8c4ed47a7dbc009f38dfd",
                  "failure": null
                }
              ],
              "execution_ref": "aba8f901c3b993c36ef7e944488f7586267f911b83e1f7475a887d855d42c7f6",
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, dusty surface and soft, smudged marks consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 52,
              "dependencies": [],
              "execution_ref": "3a5403e9dde7a669008504169fdc9c2d289bac6a3a5faf377c53081b4fc60eec",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "210d3fc05359f4006682d6c220d88a0be75f3bf395d088692f41e5fd6e1ef425",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, dusty surface and soft, smudged marks consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 52,
                  "dependencies": [],
                  "execution_ref": "3a5403e9dde7a669008504169fdc9c2d289bac6a3a5faf377c53081b4fc60eec",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "210d3fc05359f4006682d6c220d88a0be75f3bf395d088692f41e5fd6e1ef425",
                  "failure": null
                }
              ],
              "execution_ref": "5cb13a89d30247f3c37e5f69df392c4cd955370dfd004c2efe2d93db0de5ef8b",
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "db23723f26bc3ea4c6d996f496c9663049d3e0626e0f6a8bcee2d536d7eb6ee8",
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
              "execution_ref": "0fbb9ec2f7046f88dc1cec9f5afebbdedc9c2cc2b5f1c162923d30f2dd70c9aa",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "db23723f26bc3ea4c6d996f496c9663049d3e0626e0f6a8bcee2d536d7eb6ee8",
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
                  "execution_ref": "0fbb9ec2f7046f88dc1cec9f5afebbdedc9c2cc2b5f1c162923d30f2dd70c9aa",
                  "failure": null
                }
              ],
              "execution_ref": "02e0a36498b968079638d87f40a308ac542ae7279055d5c00ed060088b690a04",
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
      "agreement": 0.4,
      "coverage": 0.4,
      "label_consistency": 0.4,
      "label_distribution": {
        "unresolved": 3,
        "partial": 2
      },
      "nodes": {
        "n1": {
          "eligible": 5,
          "queried": 5,
          "activation_rate": 1.0,
          "states": {
            "unknown": 3,
            "pass": 2
          },
          "consistency": 0.4,
          "assessment": "assessed",
          "confidence": [
            0.91,
            0.88,
            0.91,
            0.91,
            0.88
          ]
        },
        "n2": {
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
            0.91,
            0.94,
            0.94,
            0.94
          ]
        },
        "n3": {
          "eligible": 2,
          "queried": 2,
          "activation_rate": 0.4,
          "states": {
            "partial": 2
          },
          "consistency": 1.0,
          "assessment": "insufficient",
          "confidence": [
            0.96,
            0.94
          ]
        }
      },
      "requirements": {
        "r1": {
          "states": {
            "unknown": 3,
            "partial": 2
          },
          "consistency": 0.4,
          "coverage": 0.4
        }
      },
      "requirement_consistency": 0.4,
      "confidence_pass": true,
      "mean_checks": 2.4,
      "mean_completion_tokens": 157.2,
      "traces": [
        {
          "program_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d",
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
              "evidence": "The edited image has a grainy, smudged appearance, but those cues alone do not establish a chalk-like medium or treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 53,
              "dependencies": [],
              "execution_ref": "fbde02a03b569417fbce2507f0f89c6ddda597b5c4de2a5ac3cecae2a14e8619",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "fail",
              "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene. Chalky grain, softened edges, and streaking are surface effects rather than a drawing-style conversion across the depicted content.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 68,
              "dependencies": [],
              "execution_ref": "c867a8e97ca1ecb00d6aa87bee3dd6f7bb0658184a987584fbb5f0821f09a780",
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
                  "evidence": "The edited image has a grainy, smudged appearance, but those cues alone do not establish a chalk-like medium or treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "fbde02a03b569417fbce2507f0f89c6ddda597b5c4de2a5ac3cecae2a14e8619",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "fail",
                  "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene. Chalky grain, softened edges, and streaking are surface effects rather than a drawing-style conversion across the depicted content.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 68,
                  "dependencies": [],
                  "execution_ref": "c867a8e97ca1ecb00d6aa87bee3dd6f7bb0658184a987584fbb5f0821f09a780",
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
              "state": "fail",
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
          "program_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "The saved observations establish a chalk-like medium, but also affirmatively state that the scene retains photographic detail rather than being converted into a drawing. Thus, some requested progress is evidenced, but the transformation is incomplete."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly chalk-like treatment: soft, powdery shading and sketchy drawn outlines across the giraffes and background, consistent with chalk marks rather than generic grain alone.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.88,
              "completion_tokens": 63,
              "dependencies": [],
              "execution_ref": "78242603f54f6dd561f7270af50a83c577b5866b0f4cb5e45cefe24c8dacdb22",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "fail",
              "evidence": "The edited image has chalk-like grain and softened, smudged colors, but the giraffes and scene retain photographic detail with effects rather than being rendered as a drawing across the depicted content.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 64,
              "dependencies": [],
              "execution_ref": "8d077ecea336e47708430689ab07d054e0b2fea788ee86badb3653785825dbfd",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "The saved observations establish a chalk-like medium, but also affirmatively state that the scene retains photographic detail rather than being converted into a drawing. Thus, some requested progress is evidenced, but the transformation is incomplete.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 74,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly chalk-like treatment: soft, powdery shading and sketchy drawn outlines across the giraffes and background, consistent with chalk marks rather than generic grain alone.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.88,
                  "completion_tokens": 63,
                  "dependencies": [],
                  "execution_ref": "78242603f54f6dd561f7270af50a83c577b5866b0f4cb5e45cefe24c8dacdb22",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "fail",
                  "evidence": "The edited image has chalk-like grain and softened, smudged colors, but the giraffes and scene retain photographic detail with effects rather than being rendered as a drawing across the depicted content.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 64,
                  "dependencies": [],
                  "execution_ref": "8d077ecea336e47708430689ab07d054e0b2fea788ee86badb3653785825dbfd",
                  "failure": null
                }
              ],
              "execution_ref": "639c9f231e309dda9e297c3faad6a902c07859de202666df690034b33f031202",
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
              "state": "fail",
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
              "state": "partial",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d",
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
              "evidence": "The edited image has a grainy, smudged appearance, but those cues alone do not establish a chalk-like medium or treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 53,
              "dependencies": [],
              "execution_ref": "b40a94451b515044ca7da2931cba8becfa9c1ddcab23bdcada8d7cbcfa6b7b6c",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "fail",
              "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene, with chalky grain and smudging layered over it rather than a drawing-style conversion across the depicted content.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 66,
              "dependencies": [],
              "execution_ref": "db26089da421c23a8ce11797a60e9dd2f508dd828a9e4e6a8df413953b01b6f0",
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
                  "evidence": "The edited image has a grainy, smudged appearance, but those cues alone do not establish a chalk-like medium or treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "b40a94451b515044ca7da2931cba8becfa9c1ddcab23bdcada8d7cbcfa6b7b6c",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "fail",
                  "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene, with chalky grain and smudging layered over it rather than a drawing-style conversion across the depicted content.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 66,
                  "dependencies": [],
                  "execution_ref": "db26089da421c23a8ce11797a60e9dd2f508dd828a9e4e6a8df413953b01b6f0",
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
              "state": "fail",
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
          "program_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d",
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
              "evidence": "The edited image has a grainy, smudged, painterly appearance, but these cues do not establish a chalk-like medium rather than generic texture or another treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 60,
              "dependencies": [],
              "execution_ref": "ee018331dce05f7df1ef9c4a7e125ac3b5f21be3058c0a1eb71adad2dd4c4ba3",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "fail",
              "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene. Chalky grain, softened edges, and streaking are surface effects rather than a drawing-style conversion across the depicted content.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 68,
              "dependencies": [],
              "execution_ref": "4ffd0563e0f450ffb524e487952d08adf904a2b18ab3ae2ea075962d30afbf8c",
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
                  "evidence": "The edited image has a grainy, smudged, painterly appearance, but these cues do not establish a chalk-like medium rather than generic texture or another treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 60,
                  "dependencies": [],
                  "execution_ref": "ee018331dce05f7df1ef9c4a7e125ac3b5f21be3058c0a1eb71adad2dd4c4ba3",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "fail",
                  "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene. Chalky grain, softened edges, and streaking are surface effects rather than a drawing-style conversion across the depicted content.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 68,
                  "dependencies": [],
                  "execution_ref": "4ffd0563e0f450ffb524e487952d08adf904a2b18ab3ae2ea075962d30afbf8c",
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
              "state": "fail",
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
          "program_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d",
          "label": "partial",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "partial",
              "applicability": "applicable",
              "source": "queried",
              "reason": "The chalk-medium support passes, establishing a visibly chalk-like treatment. The drawing-conversion support fails and affirmatively notes that the giraffes and scene retain photographic detail and rendering. Thus, some requested progress is evidenced, but the image is not fully converted into a chalk drawing."
            }
          },
          "requirements": {
            "r1": "partial"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly chalk-like treatment: soft, powdery shading and sketchy drawn outlines across the giraffes and background, consistent with chalk marks rather than generic grain alone.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.88,
              "completion_tokens": 63,
              "dependencies": [],
              "execution_ref": "bb13a7cedde27c9d725d9ba2403e8f5b0ce45fd05111c16e2c3f3ded4f652dc5",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "fail",
              "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene. Chalky grain and softened, smeared backgrounds are surface effects rather than a drawing-style conversion across the depicted content.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 67,
              "dependencies": [],
              "execution_ref": "4adf21296b86415b5923a892031c443d6b89f3236ff0446740cf811dad16d273",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "partial",
              "evidence": "The chalk-medium support passes, establishing a visibly chalk-like treatment. The drawing-conversion support fails and affirmatively notes that the giraffes and scene retain photographic detail and rendering. Thus, some requested progress is evidenced, but the image is not fully converted into a chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 87,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly chalk-like treatment: soft, powdery shading and sketchy drawn outlines across the giraffes and background, consistent with chalk marks rather than generic grain alone.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.88,
                  "completion_tokens": 63,
                  "dependencies": [],
                  "execution_ref": "bb13a7cedde27c9d725d9ba2403e8f5b0ce45fd05111c16e2c3f3ded4f652dc5",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "fail",
                  "evidence": "The edited image retains photographic detail and recognizable photo-like rendering of the giraffes and scene. Chalky grain and softened, smeared backgrounds are surface effects rather than a drawing-style conversion across the depicted content.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 67,
                  "dependencies": [],
                  "execution_ref": "4adf21296b86415b5923a892031c443d6b89f3236ff0446740cf811dad16d273",
                  "failure": null
                }
              ],
              "execution_ref": "ee27ffe7c34f6e4bdc105dfaf4053e7a321f2e49c42cbe7cf7f82db43ea661c5",
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
              "state": "fail",
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
              "state": "partial",
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
      "insufficient_activation:n3",
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
  "search_status": "unresolved",
  "stop_reason": "round_limit",
  "usage": {
    "search": 33,
    "final": 27,
    "completion_tokens_or_reserved": 6981,
    "input_tokens": 121889
  }
}
## nested-required

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
            0.94,
            0.94,
            0.94,
            0.91
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
            0.97,
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
            0.98,
            0.94,
            0.98,
            0.99,
            0.99
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
      "mean_completion_tokens": 173.8,
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing."
            }
          },
          "requirements": {
            "r1": "complete"
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
              "execution_ref": "45d5209218526f4e7b034628df8641439bef4b73b59ed4207369f2ebc58ec2a3",
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
              "execution_ref": "ab40887350b1e19f448bf1210dbf32d46965deb080a071877379cfc564b8c26a",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 63,
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
                  "execution_ref": "45d5209218526f4e7b034628df8641439bef4b73b59ed4207369f2ebc58ec2a3",
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
                  "execution_ref": "ab40887350b1e19f448bf1210dbf32d46965deb080a071877379cfc564b8c26a",
                  "failure": null
                }
              ],
              "execution_ref": "fc187956241fb4764a772f77a4374e51f8aa0aaa9c1bfcb20423cc5a69b890f8",
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, chalk-like marks across the scene, consistent with a chalk drawing treatment.",
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
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 53,
              "dependencies": [],
              "execution_ref": "4ec8ca8ecbba3e81e148d162bfdbd7c46ef3016f03db1f15d706dd7c07ec62b1",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, sketch-like rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, chalk-like marks across the scene, consistent with a chalk drawing treatment.",
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
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "4ec8ca8ecbba3e81e148d162bfdbd7c46ef3016f03db1f15d706dd7c07ec62b1",
                  "failure": null
                }
              ],
              "execution_ref": "9d7df8531cfab0af2f047244acfb968f5502713ec24d0bbb2f59dc0df91cce9e",
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
              "evidence": "The edited image has a visibly chalk-like treatment, with soft, grainy, smudged shading across the scene and subjects.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 52,
              "dependencies": [],
              "execution_ref": "8e060fdefc7a396802091ca81ebb6a8ab798874d5c3392d805dd8536a6eae71d",
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
              "execution_ref": "6ceca3a37ebb83e343b30fd59bfabdec92bcd26fc804ed69c48f2c71d246dfd4",
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
                  "evidence": "The edited image has a visibly chalk-like treatment, with soft, grainy, smudged shading across the scene and subjects.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 52,
                  "dependencies": [],
                  "execution_ref": "8e060fdefc7a396802091ca81ebb6a8ab798874d5c3392d805dd8536a6eae71d",
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
                  "execution_ref": "6ceca3a37ebb83e343b30fd59bfabdec92bcd26fc804ed69c48f2c71d246dfd4",
                  "failure": null
                }
              ],
              "execution_ref": "532881dedb009cea41b644f390da228faf7ff31f9617c8b9c396974dc4eb463d",
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
              "reason": "Both saved support observations pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks across the scene, consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 58,
              "dependencies": [],
              "execution_ref": "2f00fedb910b02306b9cc8c5e9a4ec1c78aca1dfc7dbafdd6cf761c5fbb3cfa9",
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
              "execution_ref": "6319948c33e1ed34e96efc880a465c14ad03a7ed3dca0b7fa5490a7bc67d0780",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "Both saved support observations pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.99,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks across the scene, consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 58,
                  "dependencies": [],
                  "execution_ref": "2f00fedb910b02306b9cc8c5e9a4ec1c78aca1dfc7dbafdd6cf761c5fbb3cfa9",
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
                  "execution_ref": "6319948c33e1ed34e96efc880a465c14ad03a7ed3dca0b7fa5490a7bc67d0780",
                  "failure": null
                }
              ],
              "execution_ref": "7618a040afdaf4b2bb35cde4e59b4201681e4381806f7e69d637fdbce46e49f5",
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
              "reason": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 54,
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
              "evidence": "Both saved supports pass: n1 establishes a chalk-like medium, and n2 establishes a drawn, illustrative rendering. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.99,
              "completion_tokens": 64,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 54,
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
              "execution_ref": "0de78338f248a899c74674ba662d5603322de84648c2757815ae24ec15a78c35",
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
            0.91,
            0.94,
            0.94,
            0.91,
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
            0.94,
            0.98,
            0.96,
            0.96
          ]
        },
        "n4": {
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
            0.97,
            0.97,
            0.97,
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
            0.96,
            0.96,
            0.97,
            0.97,
            0.97
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
      "mean_checks": 4.0,
      "mean_completion_tokens": 248.4,
      "traces": [
        {
          "program_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "The saved observations establish a chalk-like treatment (n1), drawing-like rendering (n2), and that the drawing treatment extends across the image (n4)."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, dusty surface and soft, smudged marks consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 52,
              "dependencies": [],
              "execution_ref": "0f39f90f1dd7792b02ec8ce7b35fd8fdf98a2b6876110bdea123781098580e9c",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 53,
              "dependencies": [],
              "execution_ref": "1c0fcc92f6be52b0ab700338d803085b16d237500b22a1f932c5262a4d82f2f2",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "pass",
              "evidence": "Drawing-like rendering extends across the giraffes, ground, trees, and sky; no substantial area remains clearly photographic. The image-wide treatment is visible beyond a localized chalk-like effect.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "1c0fcc92f6be52b0ab700338d803085b16d237500b22a1f932c5262a4d82f2f2",
                  "failure": null
                }
              ],
              "execution_ref": "066856cb04279ce28cfe560760fa5d2ee1ae88e6356b38a0d5ddb9a36f870aa7",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "The saved observations establish a chalk-like treatment (n1), drawing-like rendering (n2), and that the drawing treatment extends across the image (n4).",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 68,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, dusty surface and soft, smudged marks consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 52,
                  "dependencies": [],
                  "execution_ref": "0f39f90f1dd7792b02ec8ce7b35fd8fdf98a2b6876110bdea123781098580e9c",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "1c0fcc92f6be52b0ab700338d803085b16d237500b22a1f932c5262a4d82f2f2",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "pass",
                  "evidence": "Drawing-like rendering extends across the giraffes, ground, trees, and sky; no substantial area remains clearly photographic. The image-wide treatment is visible beyond a localized chalk-like effect.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 65,
                  "dependencies": [
                    {
                      "check_id": "n2",
                      "status": "pass",
                      "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 53,
                      "dependencies": [],
                      "execution_ref": "1c0fcc92f6be52b0ab700338d803085b16d237500b22a1f932c5262a4d82f2f2",
                      "failure": null
                    }
                  ],
                  "execution_ref": "066856cb04279ce28cfe560760fa5d2ee1ae88e6356b38a0d5ddb9a36f870aa7",
                  "failure": null
                }
              ],
              "execution_ref": "bb1a429809721337548c5da63ace1b5f845d28faa6b3236c9a350cf87df6862e",
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
              "state": "pass",
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
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "All supplied supports pass: n1 establishes a chalk-like treatment, n2 establishes drawing-like rendering, and n4 establishes that the drawing-like rendering extends across the image. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, chalk-like marks across the scene, consistent with a chalk drawing treatment.",
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
              "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.94,
              "completion_tokens": 53,
              "dependencies": [],
              "execution_ref": "4c28e3fd6fa10d77d027e6c15f3646ecfe96381917750e20dd243adf33c8150e",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "pass",
              "evidence": "Drawing-like rendering extends across the giraffes and the surrounding scene, including the sky, trees, ground, and peripheral railing; no substantial area remains clearly photographic or only locally treated.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 65,
              "dependencies": [
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "4c28e3fd6fa10d77d027e6c15f3646ecfe96381917750e20dd243adf33c8150e",
                  "failure": null
                }
              ],
              "execution_ref": "98fd21c4185398a0960b387086fecaa74c8791700cb1792af5a80583c00d705c",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "All supplied supports pass: n1 establishes a chalk-like treatment, n2 establishes drawing-like rendering, and n4 establishes that the drawing-like rendering extends across the image. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 78,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, chalk-like marks across the scene, consistent with a chalk drawing treatment.",
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
                  "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.94,
                  "completion_tokens": 53,
                  "dependencies": [],
                  "execution_ref": "4c28e3fd6fa10d77d027e6c15f3646ecfe96381917750e20dd243adf33c8150e",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "pass",
                  "evidence": "Drawing-like rendering extends across the giraffes and the surrounding scene, including the sky, trees, ground, and peripheral railing; no substantial area remains clearly photographic or only locally treated.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.97,
                  "completion_tokens": 65,
                  "dependencies": [
                    {
                      "check_id": "n2",
                      "status": "pass",
                      "evidence": "The edited image visibly renders the giraffes and surroundings with softened, sketch-like outlines and drawn shading rather than retaining a clearly photographic appearance.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.94,
                      "completion_tokens": 53,
                      "dependencies": [],
                      "execution_ref": "4c28e3fd6fa10d77d027e6c15f3646ecfe96381917750e20dd243adf33c8150e",
                      "failure": null
                    }
                  ],
                  "execution_ref": "98fd21c4185398a0960b387086fecaa74c8791700cb1792af5a80583c00d705c",
                  "failure": null
                }
              ],
              "execution_ref": "d2b3f502799908cc6bea6c6869ea657a022cb7336b4942220967d12767bdd957",
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
              "state": "pass",
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
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "All saved supports pass: n1 establishes a chalk-like treatment, n2 establishes drawing form, and n4 establishes that the drawing-like rendering extends across the image. Together they support the requested chalk drawing transformation."
            }
          },
          "requirements": {
            "r1": "complete"
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
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn outlines and a soft, illustrative appearance rather than retaining the source photograph\u2019s photographic rendering.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 55,
              "dependencies": [],
              "execution_ref": "4966a761d0e7dd8eed4b8d12f0cc8c78fd83595121c3196dac2a7a0cca7b9bae",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "pass",
              "evidence": "Drawing-like rendering extends across the giraffes and the surrounding background, including the trees, sky, and ground; no substantial area appears to retain the source photograph's rendering.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 63,
              "dependencies": [
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
                  "execution_ref": "4966a761d0e7dd8eed4b8d12f0cc8c78fd83595121c3196dac2a7a0cca7b9bae",
                  "failure": null
                }
              ],
              "execution_ref": "65395dbabc44dbca15ca1289ecc1f7a8b928042630548815a5629ff8a2950b5a",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "All saved supports pass: n1 establishes a chalk-like treatment, n2 establishes drawing form, and n4 establishes that the drawing-like rendering extends across the image. Together they support the requested chalk drawing transformation.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 77,
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
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn outlines and a soft, illustrative appearance rather than retaining the source photograph\u2019s photographic rendering.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 55,
                  "dependencies": [],
                  "execution_ref": "4966a761d0e7dd8eed4b8d12f0cc8c78fd83595121c3196dac2a7a0cca7b9bae",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "pass",
                  "evidence": "Drawing-like rendering extends across the giraffes and the surrounding background, including the trees, sky, and ground; no substantial area appears to retain the source photograph's rendering.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.97,
                  "completion_tokens": 63,
                  "dependencies": [
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
                      "execution_ref": "4966a761d0e7dd8eed4b8d12f0cc8c78fd83595121c3196dac2a7a0cca7b9bae",
                      "failure": null
                    }
                  ],
                  "execution_ref": "65395dbabc44dbca15ca1289ecc1f7a8b928042630548815a5629ff8a2950b5a",
                  "failure": null
                }
              ],
              "execution_ref": "063edcbba9ca88acf91a0f315a0d1804f28bae1d63f4317de0ed55b437a73f12",
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
              "state": "pass",
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
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "The saved observations establish a chalk-like powdery treatment (n1), drawing-like rendering (n2), and that the drawing treatment extends across the image (n4)."
            }
          },
          "requirements": {
            "r1": "complete"
          },
          "observations": [
            {
              "check_id": "n1",
              "status": "pass",
              "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.91,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "80bc13513c73a0cd722900786db47978b4f8ed7fc953b1240c739d60263b571b",
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
              "execution_ref": "6f290b5607c10185cf7b52b81c41387c4dda51f04119d0e36f4ef87e4ed53d04",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "pass",
              "evidence": "Drawing-like rendering extends across the giraffes, ground, trees, sky, and other background details; no substantial area appears to retain the source photograph's original photographic rendering.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 63,
              "dependencies": [
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
                  "execution_ref": "6f290b5607c10185cf7b52b81c41387c4dda51f04119d0e36f4ef87e4ed53d04",
                  "failure": null
                }
              ],
              "execution_ref": "41cd7b669444ed644194aed88282c55ca14beca18888e93d26e1973172690741",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "The saved observations establish a chalk-like powdery treatment (n1), drawing-like rendering (n2), and that the drawing treatment extends across the image (n4).",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
              "completion_tokens": 70,
              "dependencies": [
                {
                  "check_id": "n1",
                  "status": "pass",
                  "evidence": "The edited image has a visibly grainy, smudged surface and soft, powdery-looking marks consistent with a chalk-like drawing treatment.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.91,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "80bc13513c73a0cd722900786db47978b4f8ed7fc953b1240c739d60263b571b",
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
                  "execution_ref": "6f290b5607c10185cf7b52b81c41387c4dda51f04119d0e36f4ef87e4ed53d04",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "pass",
                  "evidence": "Drawing-like rendering extends across the giraffes, ground, trees, sky, and other background details; no substantial area appears to retain the source photograph's original photographic rendering.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.97,
                  "completion_tokens": 63,
                  "dependencies": [
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
                      "execution_ref": "6f290b5607c10185cf7b52b81c41387c4dda51f04119d0e36f4ef87e4ed53d04",
                      "failure": null
                    }
                  ],
                  "execution_ref": "41cd7b669444ed644194aed88282c55ca14beca18888e93d26e1973172690741",
                  "failure": null
                }
              ],
              "execution_ref": "4098d5779acbffe3373c97649117184815816b733858c41924c5499599123213",
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
              "state": "pass",
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
              "state": "complete",
              "skip_reason": ""
            }
          ]
        },
        {
          "program_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd",
          "label": "yes",
          "resolved": true,
          "outcomes": {
            "o1": {
              "status": "complete",
              "applicability": "applicable",
              "source": "queried",
              "reason": "The saved observations establish a chalk-like surface treatment and drawn, sketch-like rendering across the image, satisfying both the medium and whole-image drawing requirements."
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
              "execution_ref": "bc8ee90fc4d243dddfedc9fbb73f49bfa502014e55251b7a11294afadd42dee4",
              "failure": null
            },
            {
              "check_id": "n2",
              "status": "pass",
              "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.96,
              "completion_tokens": 54,
              "dependencies": [],
              "execution_ref": "54f8d0ed01744a6db3be5f01a3e813fd7ab72cafb492022cafcd40cdf575e827",
              "failure": null
            },
            {
              "check_id": "n4",
              "status": "pass",
              "evidence": "Drawing-like rendering extends across the image: both giraffes, the ground, trees, hills, sky, and peripheral fence are rendered with sketch-like outlines and shading rather than remaining photographic. This supports the extent-of-rendering proposition; it does not by itself establish the chalk medium.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.98,
              "completion_tokens": 85,
              "dependencies": [
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "54f8d0ed01744a6db3be5f01a3e813fd7ab72cafb492022cafcd40cdf575e827",
                  "failure": null
                }
              ],
              "execution_ref": "fa80b7e14b61506887fac75f05ec0fdd486652d5e310f49a560099d4636ae7dc",
              "failure": null
            },
            {
              "check_id": "n3",
              "status": "complete",
              "evidence": "The saved observations establish a chalk-like surface treatment and drawn, sketch-like rendering across the image, satisfying both the medium and whole-image drawing requirements.",
              "valid": true,
              "eligible": true,
              "queried": true,
              "confidence": 0.97,
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
                  "execution_ref": "bc8ee90fc4d243dddfedc9fbb73f49bfa502014e55251b7a11294afadd42dee4",
                  "failure": null
                },
                {
                  "check_id": "n2",
                  "status": "pass",
                  "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.96,
                  "completion_tokens": 54,
                  "dependencies": [],
                  "execution_ref": "54f8d0ed01744a6db3be5f01a3e813fd7ab72cafb492022cafcd40cdf575e827",
                  "failure": null
                },
                {
                  "check_id": "n4",
                  "status": "pass",
                  "evidence": "Drawing-like rendering extends across the image: both giraffes, the ground, trees, hills, sky, and peripheral fence are rendered with sketch-like outlines and shading rather than remaining photographic. This supports the extent-of-rendering proposition; it does not by itself establish the chalk medium.",
                  "valid": true,
                  "eligible": true,
                  "queried": true,
                  "confidence": 0.98,
                  "completion_tokens": 85,
                  "dependencies": [
                    {
                      "check_id": "n2",
                      "status": "pass",
                      "evidence": "The edited image visibly renders the giraffes and surroundings with drawn, sketch-like outlines and shading rather than retaining the source photograph\u2019s photographic appearance.",
                      "valid": true,
                      "eligible": true,
                      "queried": true,
                      "confidence": 0.96,
                      "completion_tokens": 54,
                      "dependencies": [],
                      "execution_ref": "54f8d0ed01744a6db3be5f01a3e813fd7ab72cafb492022cafcd40cdf575e827",
                      "failure": null
                    }
                  ],
                  "execution_ref": "fa80b7e14b61506887fac75f05ec0fdd486652d5e310f49a560099d4636ae7dc",
                  "failure": null
                }
              ],
              "execution_ref": "62e469d97e93c31ca1b703f27b0004490c49d427a13e28457751e35611905ee8",
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
              "state": "pass",
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
      "target_mismatch",
      "confirmation_missing_or_unqualified"
    ],
    "policy": {
      "repeats": 5,
      "agreement": 0.8,
      "consistency": 0.8,
      "confidence": 0.8,
      "minimum_eligible": 3
    },
    "reference_conflict_suspected": true
  },
  "checks": 4,
  "nested_checks": [
    "n4"
  ],
  "confirmed": false,
  "search_status": "stable_but_mismatched",
  "stop_reason": "round_limit",
  "usage": {
    "search": 43,
    "final": 35,
    "completion_tokens_or_reserved": 8407,
    "input_tokens": 122490
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
    "reason": "The requested readout is not faithful to the rubric\u2019s unresolved-evidence rule. It labels the case partial whenever one support passes and the other fails, but a failed support does not necessarily establish that the whole requested transformation is incomplete: n1 only checks for visible chalk treatment, and n2 only checks whether the content is a drawing. Their criteria allow failures based on absence of visible evidence, not necessarily evidence that the image was not transformed. The readout therefore overstates partial fulfillment. It also treats both supports failing as absent, although those failures may not establish that no requested change progressed.",
    "execution_ref": "5c0636801a2976f30653db47ccfddadfc1b8f95922d0cddb3e7d601314e140a6"
  }
}

Returned model identities: ["gpt-6-luna"]
Usage: {"limits": {"max_calls": 300, "max_completion_tokens": 384000, "reserve_calls": 80, "reserve_tokens": 81920, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 140, "completion_tokens_or_reserved": 15697, "input_tokens": 246155, "consecutive_errors": 0, "stopped": null, "final_calls": 62, "final_tokens": 3754}

Final outcomes never trigger further optimization. Missing evidence and failure slots remain in denominators.
