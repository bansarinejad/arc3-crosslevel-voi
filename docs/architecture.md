# Architecture

The runtime has five boundaries:

1. **Environment adapter** converts official frames and actions into immutable domain
   types and enforces competition-mode lifecycle restrictions.
2. **Single model backend** supports program-induction and direct-policy modes. Neither
   controller nor tests import a particular inference engine.
3. **Restricted workers** validate generated ASTs and expose only `predict` and
   `goal_value` through a narrow interface.
4. **Hypothesis pool and planner** prequentially score programs, simulate candidates, and
   compute agreement, robust plan cost, EVSI, and cross-level probe utility.
5. **Runner and recorder** enforce shared budgets and write immutable traces before any
   statistical aggregation.

The planner has content-addressed unresolved-cost policies. `endpoint-v1` is the historical
default and uses only the horizon endpoint goal for unresolved paths. The opt-in
`path-deficit-v2` policy accumulates unresolved progress deficit along the simulated path
while retaining exact completion costs and the `[4,8]` unresolved range. It belongs only
to `crosslevel-voi-runtime-v4`, whose fixed synthetic scene/compiler/registered-weight gate
failed and was preserved from clean Linux commit `989c321` in the content-addressed
synthetic admission report. It is not an admitted live runtime. Its planner-level palette,
translation, scaling, and ordering metamorphic suite
was not run, so no such invariance is attributed to the treatment.

Environment observations are 64×64 symbolic grids. `History` retains eight stable frames,
their preceding actions, action availability, terminal state, and level delta. Animation
frames may be recorded separately, but planning uses the last stable frame.

## Failure routing

- Unsafe, malformed, timed-out, or shape-invalid programs receive zero weight.
- A collapsed pool triggers at most one refresh per level and at most three batches per
  game.
- After refresh exhaustion, the same backbone selects a direct action. This is explicitly
  logged and never presented as a second model.
- `GAME_OVER` triggers the only automatic reset. No speculative reset is allowed.
- Token, action, or wall-time exhaustion ends the game run with a typed reason.
- Registration-only proposal sources and frozen implementation contracts are rejected
  before model preflight, backend creation, environment-client construction, agent
  construction, scorecard execution, and per-row matrix execution. Relabeling a failed
  runtime as Qwen cannot bypass this boundary.
