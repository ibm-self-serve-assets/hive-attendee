import React from 'react';
import type { QueenOrder } from '../types';
import { PARTS, PART_ICON, RESOURCE_ICON, RESOURCES, ROBOTS, STATIONS } from '../levels/robots';

const ITEM_WIDTH = 200; // min width of a card; cards grow to fill the row
const ITEM_GAP = 8;     // gap-2 = 8px

/** Icon of the workstation an order applies to: a resource station or a parts station. */
const stationIcon = (station: string): string | undefined => RESOURCE_ICON[station] ?? PART_ICON[station];

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const robotLabel = (id: string) => ROBOTS.find((r) => r.id === id)?.label ?? capitalize(id);

const stationLabel = (id: string) =>
  [...RESOURCES, ...STATIONS].find((s) => s.id === id)?.label ?? capitalize(id);

/** e.g. "Gatherer to upgrade the Resin workstation", "Builder to build a new Actuator workstation". */
const describeOrder = (order: QueenOrder) => {
  const robot = robotLabel(order.robot_type);
  const station = stationLabel(order.workstation_type);
  return order.action === 'add'
    ? `${robot} to build a new ${station} workstation`
    : `${robot} to upgrade the ${station} workstation`;
};

const GLYPH_COLOR = '#1F2A44';

/** Up arrow for an upgrade, plus sign for a new workstation (builder). */
const ActionGlyph: React.FC<{ action: QueenOrder['action'] }> = ({ action }) =>
  action === 'add' ? (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true" className="flex-none">
      <path d="M11 3v16M3 11h16" stroke={GLYPH_COLOR} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  ) : (
    <svg width="16" height="22" viewBox="0 0 14 22" fill="none" aria-hidden="true" className="flex-none">
      <path d="M7 20V3M1.5 8.5L7 3l5.5 5.5" stroke={GLYPH_COLOR} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );

const CrownIcon: React.FC = () => (
  <svg width="28" height="22" viewBox="0 0 28 22" fill="#1A56F0" aria-hidden="true" className="flex-none">
    <path d="M1 5l6.5 5L14 1l6.5 9L27 5l-2.5 15h-21z" />
  </svg>
);

const QueenTitle: React.FC = () => (
  <div className="flex items-center gap-2.5">
    <CrownIcon />
    <h2 className="text-[#1A56F0] font-bold text-2xl">Queen's orders</h2>
  </div>
);

/** One order: the robot, what it will do (a pill with the workstation icon and an arrow or plus), and the parts it needs. */
const OrderCard: React.FC<{ order: QueenOrder; isNext: boolean }> = ({ order, isNext }) => {
  const icon = stationIcon(order.workstation_type);
  const robot = ROBOTS.find((r) => r.id === order.robot_type);
  const parts = order.parts;
  return (
    <div
      className={`flex-1 min-w-[200px] max-w-[340px] rounded-xl px-3 py-2.5 flex flex-col gap-2 select-none ${
        isNext ? 'border-2 border-[#1A56F0] bg-[#EEF3FF]' : 'border-2 border-[#D5DDF0] bg-[#F7F9FD]'
      }`}
      title={describeOrder(order)}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {robot && <img src={robot.icon} width={34} height={34} alt="" className="flex-none" style={{ objectFit: 'contain' }} />}
          <span className="h-6 w-px bg-[#C9D3EA] flex-none" aria-hidden="true" />
          <span className="text-[#1F2A44] text-base font-semibold truncate">{robotLabel(order.robot_type)}</span>
        </div>
        <div className="flex items-center gap-1 flex-none rounded-full bg-[#DDE6F7] px-3 py-1">
          {icon ? (
            <img src={icon} width={22} height={22} alt={order.workstation_type} className="flex-none" />
          ) : (
            <span className="text-xs text-[#1F2A44]">{order.workstation_type.charAt(0).toUpperCase()}</span>
          )}
          <ActionGlyph action={order.action} />
        </div>
      </div>
      {/* No row until the parts arrive (a separate Flink job), rather than zeros. */}
      {parts && (
        <div>
          <div className="text-sm font-semibold text-[#1F2A44] mb-1.5">Parts required</div>
          <div className="flex items-center">
            {PARTS.map(({ id, label }, i) => (
              <span
                key={id}
                className={`flex-1 inline-flex items-center justify-center gap-1 ${i > 0 ? 'border-l border-[#C9D3EA]' : ''}`}
                title={label}
              >
                <img src={PART_ICON[id]} width={22} height={22} alt={label} style={{ objectFit: 'contain' }} />
                <span className="text-sm font-semibold text-[#1F2A44] tabular-nums">×{parts[id as keyof typeof parts] ?? 0}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

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
    // The row only exists while the queue has orders, so look again when that changes.
  }, [queue.length === 0]);

  if (queue.length === 0) {
    return (
      <div className="rounded-2xl bg-white border-2 border-[#C9D9FB] px-4 py-3">
        <QueenTitle />
        <div className="text-xs text-[#57606a] italic py-1">Queue is empty</div>
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
    <div className="rounded-2xl bg-white border-2 border-[#C9D9FB] px-4 py-3">
      <QueenTitle />
      <div ref={containerRef} className="flex items-stretch gap-2 pt-2 pb-1 overflow-hidden min-w-0">
        {visibleItems.map((order, idx) => (
          <OrderCard key={order.order_id} order={order} isNext={idx === 0} />
        ))}
        {showOverflow && remainingCount > 0 && (
          <div
            className="w-10 self-stretch rounded-xl flex items-center justify-center text-xs font-semibold select-none bg-[#F7F9FD] border-2 border-[#D5DDF0] text-[#1F2A44] flex-none"
            title={`${remainingCount} more order${remainingCount > 1 ? 's' : ''} in queue`}
          >
            +{remainingCount}
          </div>
        )}
      </div>
    </div>
  );
};
