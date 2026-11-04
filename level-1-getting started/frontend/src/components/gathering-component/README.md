# Gathering (React + TypeScript)

Borderless, transparent gathering graphic: a **filled hive hexagon**, two branches,
and four circles. No resource heading or bounding card is included.

## Use in your app

Copy `Gathering.tsx`, `Gathering.css`, and `gatheringModel.ts` together into your React
project. React 18+ and a bundler supporting CSS imports are required. No icon or UI
libraries are needed. For a Next.js App Router project add `'use client';` at the
top of `Gathering.tsx` (or import it from your existing client boundary).

```tsx
import { useState } from 'react';
import { Gathering, type Counts } from './index';

export function CopperGathering() {
  const [counts, setCounts] = useState<Counts>([3, 1, 0, 0]);
  return (
    <Gathering
      resourceName="Copper"
      counts={counts}
      onAdd={({ nextCounts }) => setCounts(nextCounts)}
    />
  );
}
```

## Interaction and rules

Circle order is **upper-near → upper-far → lower-near → lower-far**.
Each circle must reach 3 before the next circle can receive a Forager. Thus both
upper circles must be full before the lower row unlocks. Capacity is 12 total.
Only the next eligible circle has an add button. It appears when that circle is
hovered or its button receives keyboard focus. Touch devices show it persistently.
Native buttons support Tab, Enter, and Space. Full and locked circles have no
button. Counts cannot be decremented through this component.

Occupied circles are solid blue with a white 1, 2, or 3. Empty circles remain
gray with no numeral. There are no time labels or sector fills.

## Active motion

One small light-blue dot travels from each occupied circle toward the filled hive
hexagon. Far-circle dots follow the full arm through the near-circle position;
the opaque numbered circles cover the dots while they pass underneath.

| Circle count | Full return-trip duration |
| --- | --- |
| 0 | No dot |
| 1 | 10 seconds |
| 2 | 5 seconds |
| 3 | 3 seconds |

These are real seconds per full circle-to-hive trip. Dots repeat continuously
and have staggered phases. This is an activity cue, not a production timer or a
resource-delivery callback. Different occupied circles animate independently.
Changing a count restarts that circle's animation at its new duration.

Set `active={false}` to hide the dots; paths and counts remain visible. Resuming
restarts motion. `active` is independent of `disabled`, which controls adding.
Dots are also hidden for users who prefer reduced motion. SVG `animateMotion`
drives movement without React frame updates, interval timers, or dependencies.

## Props

| Prop | Type | Meaning |
| --- | --- | --- |
| `counts` | `readonly [Count, Count, Count, Count]` | Required controlled state; each Count is 0, 1, 2, or 3 |
| `onAdd` | `(request: AddRequest) => void \| Promise<void>` | Optional assignment callback; omit to hide add controls |
| `active` | `boolean` | Show moving dots; defaults to true |
| `readOnly` | `boolean` | Hide add controls; defaults to false |
| `disabled` | `boolean` | Prevent additions; defaults to false |
| `resourceName` | `string` | Accessible name; defaults to Resource; not visibly drawn |
| `className` | `string` | Extra root CSS class |
| `style` | `CSSProperties` | Inline root styles |

`AddRequest` includes `index` (0–3), `previousValue`, `nextValue` (1–3), and
`nextCounts` (a new tuple). The component never mutates the supplied counts.
The parent owns state and must pass the updated tuple after success. Invalid or
out-of-order state throws an explanatory error; validate persisted data before
rendering. `nextEligible()` and `addRequest()` are also exported by `gatheringModel.ts`.

## Async assignment / simulation integration

```tsx
<Gathering
  counts={counts}
  resourceName="Copper"
  active={!simulationPaused}
  disabled={availableForagers === 0 || simulationPaused}
  onAdd={async ({ index }) => {
    // Your API must validate inventory and the same sequential allocation rules.
    const authoritativeCounts = await assignForagerToCopper(index);
    setCounts(authoritativeCounts);
  }}
/>
```

The API function above is an integration placeholder. Return/await the request
promise so the component locks additions until completion. A ref also blocks
rapid duplicate clicks before React rerenders. A rejected promise leaves state
unchanged and displays its error message under the diagram. A later attempt clears
the error. If updates arrive over an event stream after your request resolves,
keep `disabled` true until the updated authoritative state arrives. The backend
should enforce inventory and concurrent request constraints as usual.

## Layout and colors

The graphic scales to its parent's width with a 600:310 aspect ratio. Suggested
width: 300–650px. The background is transparent. Scope optional overrides on the
root using these CSS custom properties:

- `--gathering-blue` (default #0755f9)
- `--gathering-gray` (default #b8c0cb)
- `--gathering-empty` (default #eef1f5)
- `--gathering-dot` (default #bde7ff)

No resource name, resource icon, or enclosing box is drawn. `Example.tsx` adds a
heading, pause/resume motion button, and reset button for demonstration only. Disabled eligible buttons remain
visible on hover, but cannot be activated. Reduced-motion preferences disable the
short hover fade and hide traveling dots. Screen readers receive circle counts and a total status; decorative motion is hidden from them.

## Run the included demo and checks

```sh
npm install
npm run dev
npm run typecheck
npm test
```

Open the local Vite URL. The demo begins at `[3, 1, 0, 0]`; Reset demo begins at
zero. The pure-logic tests cover every transition through all 12 assignments,
blocked out-of-order additions, full capacity, invalid state, and dot-duration mapping.

## Migration from earlier ZIPs

Replace the old component folder completely; do not merge over it. The old
`gathering.ts` helper is now `gatheringModel.ts`. Import from the folder entry
point: `import { Gathering, type Counts } from "./gathering-component"`.
The included `GatheringStation.tsx` goes beside that folder in `src/components`.
It is a read-only wrapper with one occupied circle based on its tier prop.
The `readOnly` prop hides plus controls without stopping motion.
