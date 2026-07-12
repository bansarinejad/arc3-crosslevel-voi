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

