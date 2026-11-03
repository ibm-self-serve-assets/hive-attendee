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

/** Up arrow for an upgrade, plus sign for a new workstation (builder). */
const ActionGlyph: React.FC<{ action: QueenOrder['action'] }> = ({ action }) => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="flex-none">
    {action === 'add' ? (
      <path d="M6 1.5v9M1.5 6h9" stroke="#031040" strokeWidth="2" strokeLinecap="round" />
    ) : (
      <path d="M6 11V2M2.5 5.5L6 2l3.5 3.5" stroke="#031040" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    )}
  </svg>
);

export interface AssemblyQueueProps {
  /** The Queen's open orders, first in first out. */
  queue: QueenOrder[];
  cancelOrder?: (orderId: string) => Promise<void> | void;
}

export const AssemblyQueue: React.FC<AssemblyQueueProps> = ({ queue, cancelOrder }) => {
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
      <div className="rounded-xl border border-[#E0E8F8] bg-white px-3 py-2">
        <div className="flex items-center justify-between">
          <h2 className="text-[#2850B8] font-bold text-sm">Queen's Orders</h2>
        </div>
        <div className="text-xs text-[#57606A] italic py-1">Queue is empty</div>
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
    <div className="rounded-xl border border-[#E0E8F8] bg-white px-3 py-2">
      <div className="flex items-center justify-between">
        <h2 className="text-[#2850B8] font-bold text-sm">Queen's Orders</h2>
      </div>
      <div ref={containerRef} className="flex items-end gap-2 pt-1.5 pb-1 overflow-hidden min-w-0">
        {visibleItems.map((order, idx) => {
          const isNext = idx === 0;
          const letter = order.robot_type.charAt(0).toUpperCase();
          const icon = stationIcon(order.station);
          return (
            <div key={order.order_id} className="relative group flex flex-col items-center gap-1 flex-none">
              <div
                className={`w-[72px] h-9 rounded-md flex items-center justify-center gap-1.5 text-md select-none ${
                  isNext
                    ? 'bg-[#FEF0CE] border-2 border-[#D48207] text-[#031040]'
                    : 'bg-[#FEF0CE] border border-[#E5B869] text-[#031040]'
                }`}
                title={describeOrder(order)}
              >
                <span>{letter}</span>
                <ActionGlyph action={order.action} />
                {icon ? (
                  <img src={icon} width={22} height={22} alt={order.station} className="flex-none" />
                ) : (
                  <span className="text-xs">{order.station.charAt(0).toUpperCase()}</span>
                )}
              </div>
              {cancelOrder && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    cancelOrder(order.order_id);
                  }}
                  title={`Cancel: ${describeOrder(order)}`}
                  className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-[#E2E8F0] hover:bg-[#DA1E28] text-[#475569] hover:text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer shadow-xs z-10 border border-white"
                >
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="none" aria-hidden="true">
                    <path d="M1 1L7 7M7 1L1 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </div>
          );
        })}
        {showOverflow && remainingCount > 0 && (
          <div
            className="w-8 h-9 rounded-md flex items-center justify-center text-xs font-semibold select-none bg-[#FEF0CE] border border-[#E5B869] text-[#031040] flex-none"
            title={`${remainingCount} more order${remainingCount > 1 ? 's' : ''} in queue`}
          >
            +{remainingCount}
          </div>
        )}
      </div>
    </div>
  );
};
