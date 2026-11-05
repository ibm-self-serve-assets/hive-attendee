# Gamifying the UI: You're Queen Now

## Overview & Goal

### The Queen's Buttons

Every workstation now has buttons that act as the Queen:

* **Gathering stations:** the **Gatherer** button orders a **Gatherer** to upgrade the station.
* **Manufacturing and assembly stations:** the **Engineer** button orders an **Engineer** to upgrade the station.
* **Every station group:** the **Builder** button, next to the dashed hexagon, orders a **Builder** to add a station.

Pressing a button sends one order to the Simulation as a `queen-worker-ordered` event.  The dashboard does **not** put the order in the queue itself.  It appears in the **Queen's Orders** only after the event has travelled through Flink into `queens_orders`, which is why there can be a moment between the click and the new icon.

### Watching the Status Change

Place an order, then watch its icon in the queue.  While earlier orders are built, it waits.  When its turn comes, assembly starts, the icon leaves the queue and the same row in `queens_orders` changes from `OPEN` to `IN_ASSEMBLY`.  You can see the row change by rerunning the Step 3 query.