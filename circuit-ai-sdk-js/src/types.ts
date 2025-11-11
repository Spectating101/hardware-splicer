/**
 * Circuit.AI JavaScript SDK Types
 * 
 * Type definitions and enumerations for the Circuit.AI API.
 */

export enum ComponentType {
  IC_CHIP = 'ic_chip',
  CAPACITOR = 'capacitor',
  RESISTOR = 'resistor',
  CONNECTOR = 'connector',
  TRANSFORMER = 'transformer',
  DIODE = 'diode',
  LED = 'led',
  TRANSISTOR = 'transistor',
  INDUCTOR = 'inductor',
  CRYSTAL = 'crystal'
}

export enum DifficultyLevel {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced'
}

export enum BackendType {
  YOLO = 'yolo',
  ENHANCED = 'enhanced'
}

export type ComponentTypeString = keyof typeof ComponentType;
export type DifficultyLevelString = keyof typeof DifficultyLevel;
export type BackendTypeString = keyof typeof BackendType;
