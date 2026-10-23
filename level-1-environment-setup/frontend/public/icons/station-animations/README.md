# Chevron animation only

`Chevrons.tsx` + `chevrons.css`: one, two or three SVG chevrons, pulsing gently from bottom to top. No extra libraries, timers, station controls or state management. Requires your existing React/TypeScript app.

## Use inside your station SVG

Copy both files together, then:

```tsx
import { Chevrons } from './Chevrons';

<svg viewBox="0 0 120 120" role="img" aria-label={stationLabel}>
  {/* Your existing hexagon */}
  <Chevrons
    tier={station.tier}
    active={station.status === 'producing'}
    inactiveOpacity={station.status === 'blocked' ? 0.4 : 1}
  />
  {/* Your existing warning badge, if drawn within this SVG */}
</svg>
```

The component renders a `<g>`, not a complete SVG. Geometry uses a 120 × 120 coordinate system. For a different coordinate system, scale/translate an enclosing `<g>` or apply the CSS directly to your existing paths as below. Color defaults to white and can be passed as `color`.

## Animate your existing chevron paths instead

Import `chevrons.css`, wrap your paths in a group, and assign bottom-to-top delays:

```tsx
<g className="hive-chevrons" data-active={isProducing}>
  <path className="hive-chevron" d={bottomChevronPath}
    style={{ animationDelay: '0s' }} />
  {/* Tier 2 or 3: */}
  <path className="hive-chevron" d={middleChevronPath}
    style={{ animationDelay: '0.24s' }} />
  {/* Tier 3 only: */}
  <path className="hive-chevron" d={topChevronPath}
    style={{ animationDelay: '0.48s' }} />
</g>
```

Render only the number of paths required for the current tier. Their existing geometry and fill are preserved. With one chevron there is a simple pulse; with two or three the pulse travels upward.

## Behavior

- All tiers repeat every 2 seconds; opacity varies from 55% to 100%.
- `active={false}` removes the animation and uses `inactiveOpacity` (default 1). Use 0.4 for blocked and 1 for paused, if desired.
- Start animation only for an actual active job. Keep existing blocked/paused status handling in your application.
- Changing state restarts the cycle. Ordinary re-renders do not, provided the component's key stays stable.
- Reduced-motion preference disables animation. Keep your existing accessible station status label; animation must not be the only state indicator.
- Adjust `2s` in CSS for cycle duration and the `0.24` multiplier in TSX for the stagger.
- Inline SVG is required to target individual paths; CSS cannot animate paths inside an SVG loaded through an `<img>`.
