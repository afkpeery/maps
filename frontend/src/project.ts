import type {Calibration, Reconstruction} from './types';

export const PROJECT_FORMAT = 'maps-project-v1';
export type ProjectFile = {
  schema: typeof PROJECT_FORMAT;
  saved_at: string;
  reconstruction: Reconstruction;
  calibration?: Calibration | null;
};

export function createProject(reconstruction: Reconstruction, calibration: Calibration | null): ProjectFile {
  return {schema: PROJECT_FORMAT, saved_at: new Date().toISOString(), reconstruction, calibration};
}

/** Strict-enough format checks to avoid crashing the 2D/3D renderers on malformed imports. */
export function parseProject(text: string): ProjectFile {
  if (text.length > 4_000_000) throw new Error('Project exceeds the 4 MB import limit.');
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object') throw new Error('Invalid project JSON.');
  const file = value as Partial<ProjectFile>;
  if (file.schema !== PROJECT_FORMAT || !file.reconstruction) throw new Error('Not a MAPS project v1 file.');
  const r = file.reconstruction;
  if (!Number.isInteger(r.nx) || !Number.isInteger(r.ny) ||
      r.nx < 1 || r.nx > 200 || r.ny < 1 || r.ny > 200 ||
      !['simulated','measured'].includes(r.source) ||
      typeof r.router_identifier !== 'string' ||
      !Number.isFinite(r.width_m) || !Number.isFinite(r.height_m) ||
      !Number.isFinite(r.cell_width_m) || !Number.isFinite(r.cell_height_m) ||
      !Array.isArray(r.rays) || !Array.isArray(r.warnings) || !Array.isArray(r.survey_targets)) {
    throw new Error('Project metadata is invalid.');
  }
  for(const key of ['attenuation','confidence','angular_diversity'] as const) {
    const grid = r[key];
    if (!Array.isArray(grid) || grid.length !== r.ny ||
        grid.some(row => !Array.isArray(row) || row.length !== r.nx || row.some(n=>typeof n!=='number' || !Number.isFinite(n)))) {
      throw new Error(`Project contains an invalid ${key} grid.`);
    }
  }
  if (!file.saved_at || typeof file.saved_at !== 'string') throw new Error('Project saved_at is invalid.');
  return file as ProjectFile;
}
