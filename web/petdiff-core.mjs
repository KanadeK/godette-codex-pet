export const CELL_WIDTH = 192;
export const CELL_HEIGHT = 208;
export const ATLAS_COLUMNS = 8;
export const ATLAS_ROWS = 11;
export const ATLAS_WIDTH = CELL_WIDTH * ATLAS_COLUMNS;
export const ATLAS_HEIGHT = CELL_HEIGHT * ATLAS_ROWS;

export const ANIMATIONS = [
  { name: "idle", row: 0, frames: 6, durations: [280, 110, 110, 140, 140, 320] },
  {
    name: "running-right",
    row: 1,
    frames: 8,
    durations: [120, 120, 120, 120, 120, 120, 120, 220],
  },
  {
    name: "running-left",
    row: 2,
    frames: 8,
    durations: [120, 120, 120, 120, 120, 120, 120, 220],
  },
  { name: "waving", row: 3, frames: 4, durations: [140, 140, 140, 280] },
  { name: "jumping", row: 4, frames: 5, durations: [140, 140, 140, 140, 280] },
  {
    name: "failed",
    row: 5,
    frames: 8,
    durations: [140, 140, 140, 140, 140, 140, 140, 240],
  },
  { name: "waiting", row: 6, frames: 6, durations: [150, 150, 150, 150, 150, 260] },
  { name: "running", row: 7, frames: 6, durations: [120, 120, 120, 120, 120, 220] },
  { name: "review", row: 8, frames: 6, durations: [150, 150, 150, 150, 150, 280] },
];

export function requiredCells() {
  const cells = [];
  for (const animation of ANIMATIONS) {
    for (let column = 0; column < animation.frames; column += 1) {
      cells.push({ row: animation.row, column, label: `${animation.name}:${column}` });
    }
  }
  // V2 stores the neutral look fallback in idle row column 6.
  cells.push({ row: 0, column: 6, label: "neutral:0" });
  for (let index = 0; index < 16; index += 1) {
    const degrees = index * 22.5;
    const label = Number.isInteger(degrees)
      ? String(degrees).padStart(3, "0")
      : degrees.toFixed(1).padStart(5, "0");
    cells.push({
      row: 9 + Math.floor(index / 8),
      column: index % 8,
      label: `look:${label}`,
    });
  }
  return cells;
}

function assertAtlas(image, name) {
  if (!image || image.width !== ATLAS_WIDTH || image.height !== ATLAS_HEIGHT) {
    throw new Error(`${name} must be ${ATLAS_WIDTH} x ${ATLAS_HEIGHT} RGBA pixels`);
  }
  if (!image.data || image.data.length !== ATLAS_WIDTH * ATLAS_HEIGHT * 4) {
    throw new Error(`${name} has an invalid RGBA buffer`);
  }
}

function bboxCenter(bounds) {
  if (bounds.right < bounds.left || bounds.bottom < bounds.top) {
    return [0, 0];
  }
  return [(bounds.left + bounds.right + 1) / 2, (bounds.top + bounds.bottom + 1) / 2];
}

export function compareAtlasData(baseline, candidate, options = {}) {
  assertAtlas(baseline, "Baseline");
  assertAtlas(candidate, "Candidate");
  const tolerance = options.channelTolerance ?? 0;
  if (!Number.isInteger(tolerance) || tolerance < 0 || tolerance > 255) {
    throw new Error("channelTolerance must be an integer from 0 to 255");
  }

  const cells = [];
  for (const cell of requiredCells()) {
    let changedPixels = 0;
    let changedVisiblePixels = 0;
    let visiblePixels = 0;
    const beforeBounds = {
      left: CELL_WIDTH,
      top: CELL_HEIGHT,
      right: -1,
      bottom: -1,
    };
    const afterBounds = {
      left: CELL_WIDTH,
      top: CELL_HEIGHT,
      right: -1,
      bottom: -1,
    };

    for (let y = 0; y < CELL_HEIGHT; y += 1) {
      for (let x = 0; x < CELL_WIDTH; x += 1) {
        const atlasX = cell.column * CELL_WIDTH + x;
        const atlasY = cell.row * CELL_HEIGHT + y;
        const offset = (atlasY * ATLAS_WIDTH + atlasX) * 4;
        let changed = false;
        for (let channel = 0; channel < 4; channel += 1) {
          if (
            Math.abs(baseline.data[offset + channel] - candidate.data[offset + channel]) >
            tolerance
          ) {
            changed = true;
          }
        }
        const beforeVisible = baseline.data[offset + 3] > 0;
        const afterVisible = candidate.data[offset + 3] > 0;
        if (beforeVisible) {
          beforeBounds.left = Math.min(beforeBounds.left, x);
          beforeBounds.top = Math.min(beforeBounds.top, y);
          beforeBounds.right = Math.max(beforeBounds.right, x);
          beforeBounds.bottom = Math.max(beforeBounds.bottom, y);
        }
        if (afterVisible) {
          afterBounds.left = Math.min(afterBounds.left, x);
          afterBounds.top = Math.min(afterBounds.top, y);
          afterBounds.right = Math.max(afterBounds.right, x);
          afterBounds.bottom = Math.max(afterBounds.bottom, y);
        }
        if (beforeVisible || afterVisible) {
          visiblePixels += 1;
          if (changed) changedVisiblePixels += 1;
        }
        if (changed) changedPixels += 1;
      }
    }

    const beforeCenter = bboxCenter(beforeBounds);
    const afterCenter = bboxCenter(afterBounds);
    const bboxShiftPx = Math.hypot(
      afterCenter[0] - beforeCenter[0],
      afterCenter[1] - beforeCenter[1],
    );
    cells.push({
      ...cell,
      changed: changedPixels > 0,
      changedPixels,
      changedRatio: changedPixels / (CELL_WIDTH * CELL_HEIGHT),
      visibleChangedPixels: changedVisiblePixels,
      visibleChangedRatio: changedVisiblePixels / Math.max(1, visiblePixels),
      bboxShiftPx,
    });
  }

  const changed = cells.filter((cell) => cell.changed);
  return {
    schemaVersion: 1,
    cells,
    summary: {
      comparedCells: cells.length,
      changedCells: changed.length,
      changedPixels: changed.reduce((sum, cell) => sum + cell.changedPixels, 0),
      largestCellChangeRatio: Math.max(0, ...changed.map((cell) => cell.changedRatio)),
      largestBboxShiftPx: Math.max(0, ...changed.map((cell) => cell.bboxShiftPx)),
    },
  };
}

export function directionCell(degrees) {
  const normalized = ((degrees % 360) + 360) % 360;
  const index = Math.round(normalized / 22.5) % 16;
  return {
    row: 9 + Math.floor(index / 8),
    column: index % 8,
    degrees: index * 22.5,
  };
}
