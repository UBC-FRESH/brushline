Planning brief
==============

The planning brief is generated on demand from the private network artifact set. It combines the
selected plan, planning stack, policy comparisons, caveats, and reproduction metadata into one
document.

Open it in the studio
---------------------

The network instance has a **Planning brief** link. HTML opens inline in a new tab. Markdown is
downloaded as an attachment.

Direct endpoints:

.. code-block:: text

   GET /api/studio/network/brief?instance_id=bc-hydro-network&format=html
   GET /api/studio/network/brief?instance_id=bc-hydro-network&format=markdown
   GET /api/studio/network/brief?instance_id=bc-hydro-network&format=html&download=1

The HTML document is self-contained and print-friendly. It contains no external assets.

Read it critically
------------------

The brief is a lab-review artifact. It is not a new optimization result and it does not remove the
underlying assumptions. Before using a number, check:

- whether the page describes an exact result or a heuristic search state;
- whether the scenario is a band, a sampled constraint, a recourse policy, or a forecast;
- whether the result is from the 59-segment prototype or a replicated scale case;
- whether the page says the result is field-calibrated or asset-owner approved.

The full content contract is in :doc:`../reference/planning-brief`.
