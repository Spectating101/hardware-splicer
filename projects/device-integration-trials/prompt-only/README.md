# Digital builds from a description

These trials used the HS text provider and local digital builders. The only user-supplied input was text. HS supplied the registered donor models.

| Request | Digital result |
| --- | --- |
| Convert a classic Ender-3 for an 11 mm pen. Use a 13 × 9 cm drawing area, 4 mm lift and draw a sailboat with two waves. | HS generated a clamp model and five drawing strokes. The verifier checked the generated SVG and simulated pen motion. [Preview](sailboat-preview.png) · [CAD, BOM and simulation](sailboat-study.zip) · [Original brief and measurements](sailboat-result.json) |
| Keep the boat and waves, add a triangular flag to the mast, and switch to a 9 mm pen. | After an intermediate numeric revision to 10.5 mm, the follow-up prompt changed the clamp to 9 mm. The revised drawing kept all five original strokes and added a sixth. The drawing area and lift were retained. [Revised preview](sailboat-flag-preview.png) · [Revised package](sailboat-flag.zip) · [Revision measurements](flag-result.json) |
| Estimate whether a five-inch FieldDeck cyberdeck can run for three hours with the Raspberry Pi drawing 1.35 A under load. | The simulation estimated 2.55–3.60 hours. The lower estimate misses the requested minimum by 27 minutes. [Original brief and results](cyberdeck-result.json) |
| Design a tabletop hand-towel folding machine. | HS identified fabric handling and folding as missing capabilities. It returned an explanation and created no project. [Response](towel-folder-result.json) |

All measurements here come from digital models. The packages include assembly geometry and the assumptions used by the corresponding study.
