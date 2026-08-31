import type { PcbGeometry, ValidationIssue } from './cad-types';

const passive = (ref: string, value: string, x: number, y: number, rot_deg = 0) => ({
  ref,
  value,
  footprint: ref.startsWith('R')
    ? 'Resistor_SMD:R_0603_1608Metric'
    : 'Capacitor_SMD:C_0603_1608Metric',
  layer: 'F.Cu',
  at: { x, y, rot_deg },
});

export const workbenchPcbGeometry: PcbGeometry = {
  board: {
    bbox_mm: { min_x: 0, min_y: 0, max_x: 110, max_y: 72, width: 110, height: 72 },
  },
  nets: [
    { id: 0, name: '' },
    { id: 1, name: 'GND' },
    { id: 2, name: '+12V_SYS' },
    { id: 3, name: '+5V_SYS' },
    { id: 4, name: '+3V3_AUX' },
    { id: 5, name: 'USB3_TX' },
    { id: 6, name: 'PCIE_NVME' },
    { id: 7, name: 'DP_AUX' },
  ],
  footprints: [
    { ref: 'U1', value: 'x86 SoC', footprint: 'Package_BGA:BGA-256_22x22mm', layer: 'F.Cu', at: { x: 45, y: 32, rot_deg: 0 } },
    { ref: 'U2', value: 'Platform controller', footprint: 'Package_QFN:QFN-64_9x9mm', layer: 'F.Cu', at: { x: 70, y: 37, rot_deg: 0 } },
    { ref: 'U3', value: 'USB-C PD controller', footprint: 'Package_QFN:QFN-32_5x5mm', layer: 'F.Cu', at: { x: 91, y: 57, rot_deg: 0 } },
    { ref: 'U4', value: '3V3 regulator', footprint: 'Package_SO:SOIC-8_3.9x4.9mm', layer: 'F.Cu', at: { x: 24, y: 22, rot_deg: 90 } },
    { ref: 'J1', value: 'USB-C power/data', footprint: 'Connector_USB:USB_C_Receptacle', layer: 'F.Cu', at: { x: 104, y: 57, rot_deg: 90 } },
    { ref: 'J2', value: 'HDMI', footprint: 'Connector_HDMI:HDMI_A', layer: 'F.Cu', at: { x: 103, y: 20, rot_deg: 90 } },
    { ref: 'J3', value: 'Ethernet', footprint: 'Connector_RJ:RJ45', layer: 'F.Cu', at: { x: 96, y: 8, rot_deg: 0 } },
    { ref: 'J4', value: 'NVMe M.2', footprint: 'Connector:Socket_M2_Key_M', layer: 'F.Cu', at: { x: 27, y: 57, rot_deg: 0 } },
    { ref: 'J5', value: 'Display eDP', footprint: 'Connector:Conn_01x30_P0.50mm', layer: 'F.Cu', at: { x: 8, y: 35, rot_deg: 90 } },
    { ref: 'L1', value: '2.2uH', footprint: 'Inductor_SMD:L_6.0x6.0mm', layer: 'F.Cu', at: { x: 28, y: 31, rot_deg: 0 } },
    { ref: 'L2', value: '1.0uH', footprint: 'Inductor_SMD:L_4.0x4.0mm', layer: 'F.Cu', at: { x: 82, y: 55, rot_deg: 0 } },
    { ref: 'Y1', value: '24MHz', footprint: 'Crystal:Crystal_SMD_3.2x2.5mm', layer: 'F.Cu', at: { x: 73, y: 25, rot_deg: 0 } },
    { ref: 'Q1', value: 'Power MOSFET', footprint: 'Package_DFN_QFN:DFN-8_5x6mm', layer: 'F.Cu', at: { x: 83, y: 62, rot_deg: 0 } },
    passive('R1', '10k', 61, 22),
    passive('R2', '10k', 64, 22),
    passive('R3', '100R', 78, 44, 90),
    passive('R4', '100R', 80, 44, 90),
    passive('R5', '5k1', 95, 49),
    passive('R6', '5k1', 98, 49),
    passive('C1', '22uF', 31, 23),
    passive('C2', '22uF', 34, 23),
    passive('C3', '100nF', 35, 47),
    passive('C4', '100nF', 39, 47),
    passive('C5', '100nF', 51, 48),
    passive('C6', '100nF', 55, 48),
    passive('C7', '10uF', 86, 50),
    passive('C8', '10uF', 89, 50),
    { ref: 'MH1', value: 'M3', footprint: 'MountingHole:MountingHole_3.2mm', layer: 'F.Cu', at: { x: 6, y: 6, rot_deg: 0 } },
    { ref: 'MH2', value: 'M3', footprint: 'MountingHole:MountingHole_3.2mm', layer: 'F.Cu', at: { x: 104, y: 66, rot_deg: 0 } },
  ],
  segments: [
    { start: { x: 12, y: 14 }, end: { x: 39, y: 29 }, width_mm: 0.45, layer: 'F.Cu', net: { id: 2, name: '+12V_SYS' } },
    { start: { x: 39, y: 29 }, end: { x: 57, y: 29 }, width_mm: 0.8, layer: 'F.Cu', net: { id: 2, name: '+12V_SYS' } },
    { start: { x: 57, y: 29 }, end: { x: 82, y: 55 }, width_mm: 0.55, layer: 'F.Cu', net: { id: 3, name: '+5V_SYS' } },
    { start: { x: 82, y: 55 }, end: { x: 101, y: 57 }, width_mm: 0.75, layer: 'F.Cu', net: { id: 3, name: '+5V_SYS' } },
    { start: { x: 24, y: 22 }, end: { x: 39, y: 32 }, width_mm: 0.32, layer: 'F.Cu', net: { id: 4, name: '+3V3_AUX' } },
    { start: { x: 50, y: 34 }, end: { x: 65, y: 37 }, width_mm: 0.22, layer: 'F.Cu', net: { id: 5, name: 'USB3_TX' } },
    { start: { x: 65, y: 37 }, end: { x: 90, y: 55 }, width_mm: 0.22, layer: 'F.Cu', net: { id: 5, name: 'USB3_TX' } },
    { start: { x: 40, y: 38 }, end: { x: 31, y: 54 }, width_mm: 0.24, layer: 'F.Cu', net: { id: 6, name: 'PCIE_NVME' } },
    { start: { x: 42, y: 39 }, end: { x: 34, y: 55 }, width_mm: 0.24, layer: 'F.Cu', net: { id: 6, name: 'PCIE_NVME' } },
    { start: { x: 39, y: 30 }, end: { x: 13, y: 35 }, width_mm: 0.2, layer: 'F.Cu', net: { id: 7, name: 'DP_AUX' } },
    { start: { x: 73, y: 34 }, end: { x: 98, y: 22 }, width_mm: 0.2, layer: 'F.Cu', net: { id: 7, name: 'DP_AUX' } },
    { start: { x: 57, y: 46 }, end: { x: 73, y: 43 }, width_mm: 0.2, layer: 'B.Cu', net: { id: 1, name: 'GND' } },
    { start: { x: 18, y: 65 }, end: { x: 94, y: 65 }, width_mm: 0.4, layer: 'B.Cu', net: { id: 1, name: 'GND' } },
  ],
  vias: [
    { x: 57, y: 46, size_mm: 1.0, drill_mm: 0.45, net: { id: 1, name: 'GND' } },
    { x: 61, y: 46, size_mm: 1.0, drill_mm: 0.45, net: { id: 1, name: 'GND' } },
    { x: 65, y: 46, size_mm: 1.0, drill_mm: 0.45, net: { id: 1, name: 'GND' } },
    { x: 69, y: 46, size_mm: 1.0, drill_mm: 0.45, net: { id: 1, name: 'GND' } },
    { x: 83, y: 52, size_mm: 1.1, drill_mm: 0.5, net: { id: 3, name: '+5V_SYS' } },
    { x: 88, y: 52, size_mm: 1.1, drill_mm: 0.5, net: { id: 3, name: '+5V_SYS' } },
  ],
  edgeLines: [
    { start: { x: 0, y: 0 }, end: { x: 110, y: 0 } },
    { start: { x: 110, y: 0 }, end: { x: 110, y: 72 } },
    { start: { x: 110, y: 72 }, end: { x: 0, y: 72 } },
    { start: { x: 0, y: 72 }, end: { x: 0, y: 0 } },
  ],
  silkText: [
    { layer: 'F.SilkS', text: 'HS x86 REPRESENTATIVE FIXTURE', at: { x: 37, y: 6, rot_deg: 0 }, size_mm: 1.4 },
    { layer: 'F.SilkS', text: 'CPU', at: { x: 43, y: 18, rot_deg: 0 }, size_mm: 1.1 },
    { layer: 'F.SilkS', text: 'NVME', at: { x: 25, y: 67, rot_deg: 0 }, size_mm: 1.0 },
    { layer: 'F.SilkS', text: 'USB-C / PD', at: { x: 83, y: 68, rot_deg: 0 }, size_mm: 1.0 },
  ],
};

export const workbenchPcbIssues: ValidationIssue[] = [
  {
    severity: 'warning',
    component: 'J1',
    issue: 'DC input profile unresolved',
    solution: 'Characterize the donor board power envelope before selecting the final PD bridge.',
  },
  {
    severity: 'info',
    component: 'U1',
    issue: 'Representative geometry only',
    solution: 'Replace this fixture with measured/imported donor geometry once board identity is verified.',
  },
];
