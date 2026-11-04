import { useState } from 'react';
import { Gathering, type Counts } from './Gathering';
export function Example() {
  const [counts, setCounts] = useState<Counts>([3, 1, 0, 0]);
  const [active, setActive] = useState(true);
  return <main style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'system-ui' }}>
    <h2>Copper</h2>
    <Gathering resourceName="Copper" active={active} counts={counts} onAdd={({ nextCounts }) => setCounts(nextCounts)} />
    <button onClick={() => setActive(value => !value)}>{active ? 'Pause motion' : 'Resume motion'}</button>
    <button onClick={() => setCounts([0, 0, 0, 0])}>Reset demo</button>
  </main>;
}
