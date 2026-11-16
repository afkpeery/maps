export type Measurement = {
  tx_x: number; tx_y: number; rx_x: number; rx_y: number;
  rssi_dbm: number; baseline_dbm_at_1m: number; path_loss_exponent: number;
  label?: string;
};
export type Reconstruction = {
  source: 'measured' | 'simulated'; router_identifier: string;
  nx: number; ny: number; width_m: number; height_m: number;
  cell_width_m: number; cell_height_m: number;
  attenuation: number[][]; confidence: number[][]; angular_diversity: number[][]; obstruction_threshold: number;
  measurements: number; unique_paths: number; outliers_rejected: number;
  survey_targets: {x_m:number;y_m:number;support:number;angular_bins:number;reason:string}[];
  transmitter_positions: number; receiver_positions: number;
  coverage_pct: number; holdout_mae_db: number | null;
  spatially_observable: boolean; warnings: string[];
  rays: {tx_x: number; tx_y: number; rx_x: number; rx_y: number}[];
  model_description: string;
};
export type ViewMode = '2d' | '3d';
export type Layer = 'attenuation' | 'confidence';
