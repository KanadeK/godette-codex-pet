import assert from "node:assert/strict";
import test from "node:test";

import {
  ATLAS_HEIGHT,
  ATLAS_WIDTH,
  CELL_HEIGHT,
  CELL_WIDTH,
  compareAtlasData,
  directionCell,
  requiredCells,
} from "../petdiff-core.mjs";

function blankAtlas() {
  return {
    width: ATLAS_WIDTH,
    height: ATLAS_HEIGHT,
    data: new Uint8ClampedArray(ATLAS_WIDTH * ATLAS_HEIGHT * 4),
  };
}

function pixel(atlas, row, column, x, y, rgba) {
  const atlasX = column * CELL_WIDTH + x;
  const atlasY = row * CELL_HEIGHT + y;
  atlas.data.set(rgba, (atlasY * ATLAS_WIDTH + atlasX) * 4);
}

test("the browser contract contains 74 required cells", () => {
  assert.equal(requiredCells().length, 74);
  assert.deepEqual(directionCell(89), { row: 9, column: 4, degrees: 90 });
  assert.deepEqual(directionCell(-1), { row: 9, column: 0, degrees: 0 });
});

test("identical atlases pass with no changed cells", () => {
  const baseline = blankAtlas();
  const candidate = blankAtlas();
  pixel(baseline, 0, 0, 20, 20, [20, 80, 120, 255]);
  pixel(candidate, 0, 0, 20, 20, [20, 80, 120, 255]);
  const report = compareAtlasData(baseline, candidate);
  assert.equal(report.summary.comparedCells, 74);
  assert.equal(report.summary.changedCells, 0);
});

test("used-cell changes are measured and unused-cell changes are ignored", () => {
  const baseline = blankAtlas();
  const candidate = blankAtlas();
  pixel(baseline, 0, 0, 20, 20, [20, 80, 120, 255]);
  pixel(candidate, 0, 0, 20, 20, [30, 80, 120, 255]);
  pixel(candidate, 0, 7, 20, 20, [255, 255, 255, 255]);
  const strict = compareAtlasData(baseline, candidate);
  assert.equal(strict.summary.changedCells, 1);
  assert.equal(strict.cells[0].changedPixels, 1);

  const tolerant = compareAtlasData(baseline, candidate, { channelTolerance: 10 });
  assert.equal(tolerant.summary.changedCells, 0);
});

test("invalid browser inputs fail with actionable messages", () => {
  const atlas = blankAtlas();
  assert.throws(
    () => compareAtlasData({ width: 1, height: 1, data: [] }, atlas),
    /Baseline must be/,
  );
  assert.throws(
    () => compareAtlasData(atlas, blankAtlas(), { channelTolerance: 256 }),
    /channelTolerance/,
  );
});
