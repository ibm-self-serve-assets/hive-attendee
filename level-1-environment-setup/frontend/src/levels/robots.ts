// ── Resource gathering ────────────────────────────────────────────────────────
export const GATHERING_ORDER = ['copper', 'energy', 'metals', 'resin', 'silicon'];

export const RESOURCES: { id: string; label: string; icon: string }[] = [
  { id: 'copper',  label: 'Copper',  icon: '/icons/svg/resource_copper.svg' },
  { id: 'energy',  label: 'Energy',  icon: '/icons/svg/resources_energy.svg' },
  { id: 'metals',  label: 'Metals',  icon: '/icons/svg/resources_metals.svg' },
  { id: 'resin',   label: 'Resin',   icon: '/icons/svg/resources_resin.svg' },
  { id: 'silicon', label: 'Silicon', icon: '/icons/svg/resources_silicon.svg' },
];

export const RESOURCE_ICON: Record<string, string> = {
  energy:    '/icons/svg/resources_energy.svg',
  resin:     '/icons/svg/resources_resin.svg',
  silicon:   '/icons/svg/resources_silicon.svg',
  metals:    '/icons/svg/resources_metals.svg',
  copper:    '/icons/svg/resource_copper.svg',
};

// ── Parts manufacturing ───────────────────────────────────────────────────────
export const STATIONS: { id: string; label: string; icon: string; output_type: string }[] = [
  { id: 'actuator_fabrication', label: 'Actuator Fabrication', icon: '/icons/svg/parts_actuator.svg',    output_type: 'actuator' },
  { id: 'battery_assembly',     label: 'Battery Assembly',     icon: '/icons/svg/parts_battery.svg',     output_type: 'battery' },
  { id: 'structural_molding',   label: 'Chassis Molding',      icon: '/icons/svg/parts_chassis.svg',     output_type: 'chassis' },
  { id: 'electronics_assembly', label: 'Electronics Assembly', icon: '/icons/svg/parts_electronics.svg', output_type: 'electronics' },
];

export const ROBOTS: { id: string; station_id: string; label: string; icon: string }[] = [
  { id: 'engineer', station_id: 'worker_assembly',  label: 'Engineer', icon: '/icons/svg/robot_engineer_body.svg' },
  { id: 'gatherer',  station_id: 'gatherer_assembly', label: 'Gatherer',  icon: '/icons/svg/robot_gatherer_body.svg' },
  { id: 'builder',  station_id: 'builder_assembly', label: 'Builder',  icon: '/icons/svg/robot_builder_body.svg' },
];

export const PARTS: { id: string; label: string; icon: string }[] = [
  { id: 'actuator',    label: 'Actuators',   icon: '/icons/svg/parts_actuator.svg' },
  { id: 'battery',     label: 'Batteries',   icon: '/icons/svg/parts_battery.svg' },
  { id: 'chassis',     label: 'Chassis',     icon: '/icons/svg/parts_chassis.svg' },
  { id: 'electronics', label: 'Electronics', icon: '/icons/svg/parts_electronics.svg' },
];

export const PART_ICON: Record<string, string> = {
  chassis:     '/icons/svg/parts_chassis.svg',
  electronics: '/icons/svg/parts_electronics.svg',
  actuator:    '/icons/svg/parts_actuator.svg',
  battery:     '/icons/svg/parts_battery.svg',
};

