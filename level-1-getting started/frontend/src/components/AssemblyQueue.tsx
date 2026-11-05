import React from 'react';
import type { QueenOrder } from '../types';
import { PART_ICON, RESOURCE_ICON, RESOURCES, ROBOTS, STATIONS } from '../levels/robots';

const ITEM_WIDTH = 72; // w-[72px]
const ITEM_GAP = 8;    // gap-2 = 8px

/** Icon of the workstation an order applies to: a resource station or a parts station. */
const stationIcon = (station: string): string | undefined => RESOURCE_ICON[station] ?? PART_ICON[station];

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const robotLabel = (id: string) => ROBOTS.find((r) => r.id === id)?.label ?? capitalize(id);

const stationLabel = (id: string) =>
  [...RESOURCES, ...STATIONS].find((s) => s.id === id)?.label ?? capitalize(id);

/** e.g. "Gatherer to upgrade the Resin workstation", "Builder to build a new Actuator workstation". */
const describeOrder = (order: QueenOrder) => {
  const robot = robotLabel(order.robot_type);
  const station = stationLabel(order.station);
  return order.action === 'add'
    ? `${robot} to build a new ${station} workstation`
    : `${robot} to upgrade the ${station} workstation`;
};

/** Up arrow for an upgrade, plus sign for a new workstation (builder). 28px tall, like the station icon. */
const ActionGlyph: React.FC<{ action: QueenOrder['action'] }> = ({ action }) =>
  action === 'add' ? (
    <svg width="28" height="28" viewBox="0 0 22 22" fill="none" aria-hidden="true" className="flex-none">
      <path d="M11 2v18M2 11h18" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  ) : (
    <svg width="18" height="28" viewBox="0 0 14 22" fill="none" aria-hidden="true" className="flex-none">
      <path d="M7 20V2M1.5 7.5L7 2l5.5 5.5" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );

export interface AssemblyQueueProps {
  /** The Queen's open orders, first in first out. */
  queue: QueenOrder[];
}

export const AssemblyQueue: React.FC<AssemblyQueueProps> = ({ queue }) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = React.useState<number>(0);

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const updateWidth = () => {
      setContainerWidth(el.getBoundingClientRect().width);
    };

    updateWidth();

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentBoxSize) {
          const contentBox = Array.isArray(entry.contentBoxSize)
            ? entry.contentBoxSize[0]
            : entry.contentBoxSize;
          if (contentBox) {
            setContainerWidth(contentBox.inlineSize);
            continue;
          }
        }
        setContainerWidth(entry.contentRect.width);
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (queue.length === 0) {
    return (
      <div className="rounded-2xl bg-[#1232D0] px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-white font-bold text-base">Queen's orders</h2>
        </div>
        <div className="text-xs text-white/70 italic py-1">Queue is empty</div>
      </div>
    );
  }

  const maxSlots =
    containerWidth > 0
      ? Math.floor((containerWidth + ITEM_GAP) / (ITEM_WIDTH + ITEM_GAP))
      : queue.length;

  const showOverflow = maxSlots > 0 && queue.length > maxSlots;
  const visibleCount = showOverflow ? Math.max(0, maxSlots - 1) : queue.length;
  const visibleItems = queue.slice(0, visibleCount);
  const remainingCount = queue.length - visibleCount;

  return (
    <div className="rounded-2xl bg-[#1232D0] px-4 py-3">
      <div className="flex items-center justify-between">
        <h2 className="text-white font-bold text-base">Queen's orders</h2>
      </div>
      <div ref={containerRef} className="flex items-end gap-2 pt-2 pb-1 overflow-hidden min-w-0">
        {visibleItems.map((order, idx) => {
          const isNext = idx === 0;
          const icon = stationIcon(order.station);
          return (
            <div key={order.order_id} className="flex flex-col items-center gap-1 flex-none">
              <div
                className={`w-[72px] h-11 rounded-xl flex items-center justify-center gap-1.5 text-md select-none bg-[#0C1850] ${
                  isNext ? 'border-2 border-[#F5B84A]' : 'border-2 border-transparent'
                }`}
                title={describeOrder(order)}
              >
                <ActionGlyph action={order.action} />
                {icon ? (
                  <img src={icon} width={28} height={28} alt={order.station} className="flex-none" />
                ) : (
                  <span className="text-xs">{order.station.charAt(0).toUpperCase()}</span>
                )}
              </div>
            </div>
          );
        })}
        {showOverflow && remainingCount > 0 && (
          <div
            className="w-8 h-11 rounded-xl flex items-center justify-center text-xs font-semibold select-none bg-[#0C1850] text-white flex-none"
            title={`${remainingCount} more order${remainingCount > 1 ? 's' : ''} in queue`}
          >
            +{remainingCount}
          </div>
        )}
      </div>
    </div>
  );
};
