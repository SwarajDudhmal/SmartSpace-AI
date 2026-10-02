export type FurnitureItem = {
  id?: string;
  type: string;
  label?: string;
  x: number;
  y: number;
  width: number;
  depth: number;
  height?: number;
  rotation?: number;
  cost?: number;
};

export type RoomLayout = {
  id?: string;
  name?: string;
  room_type?: string;
  room_width?: number;
  room_length?: number;
  width?: number;
  length?: number;
  budget?: number;
  style?: string;
  door?: Record<string, unknown>;
  windows?: Array<Record<string, unknown>>;
  furniture: FurnitureItem[];
  metrics?: {
    total_cost?: number;
    circulation_ratio?: number;
    ergonomics_score?: number;
    collision_count?: number;
  };
  state_133d?: number[];
  [key: string]: unknown;
};

export type RoomPreset = {
  id: string;
  name: string;
  room_type: string;
  room_width_m: number;
  room_length_m: number;
  budget_inr: number;
  style_tag: string;
  circulation_ratio: number;
  expert_ergonomic_score: number;
  estimated_cost_inr: number;
  thumbnail_url?: string;
  description?: string;
  featured?: number | boolean;
  layout: RoomLayout;
};

export type RecommendationBundle = {
  id: string;
  name: string;
  style: string;
  total_cost_inr: number;
  budget_cap_inr: number;
  omitted_categories?: string[];
  layout: RoomLayout;
  metrics: NonNullable<RoomLayout['metrics']>;
  validation: { valid: boolean; engine?: string };
  items: Array<{ thumbnail_url?: string; style_tag?: string }>;
};

export type LayoutLoadedDetail = {
  layout: RoomLayout;
  bundle?: Record<string, unknown>;
  source: 'homepage' | 'recommendation';
};

declare global {
  interface Window {
    smartSpaceStudioBudget?: number;
    smartSpaceMdpState?: number[];
  }
}
