import {
  ANIMATIONS,
  ATLAS_HEIGHT,
  ATLAS_WIDTH,
  CELL_HEIGHT,
  CELL_WIDTH,
  directionCell,
} from "./petdiff-core.mjs";

const heroCanvas = document.querySelector("#godette-canvas");
const heroContext = heroCanvas.getContext("2d");
const candidateInput = document.querySelector("#candidate-file");
const compareButton = document.querySelector("#compare-button");
const resetButton = document.querySelector("#reset-candidate");
const toleranceInput = document.querySelector("#tolerance");
const toleranceValue = document.querySelector("#tolerance-value");
const loadStatus = document.querySelector("#load-status");
const verdict = document.querySelector("#result-verdict");
const summary = document.querySelector("#result-summary");
const changedList = document.querySelector("#changed-list");
const previewTitle = document.querySelector("#preview-title");
const beforeCanvas = document.querySelector("#before-canvas");
const afterCanvas = document.querySelector("#after-canvas");
const deltaCanvas = document.querySelector("#delta-canvas");
const themeSelect = document.querySelector("#theme-select");

const worker = new Worker("./petdiff-worker.mjs", { type: "module" });
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const pending = new Map();
let requestId = 0;
let baselineAtlas;
let candidateAtlas;
let candidateName = "Bundled Godette";
let manualLook = null;
let animationStart = performance.now();

document.querySelector("#lab-form").addEventListener("submit", (event) => {
  event.preventDefault();
});

themeSelect.addEventListener("change", () => {
  if (themeSelect.value === "auto") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = themeSelect.value;
  }
});

worker.addEventListener("message", (event) => {
  const callback = pending.get(event.data.id);
  if (!callback) return;
  pending.delete(event.data.id);
  if (event.data.ok) callback.resolve(event.data.report);
  else callback.reject(new Error(event.data.error));
});

function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.decoding = "async";
    image.addEventListener("load", () => resolve(image), { once: true });
    image.addEventListener("error", () => reject(new Error("Could not decode the atlas.")), {
      once: true,
    });
    image.src = source;
  });
}

function assertDimensions(image) {
  if (image.naturalWidth !== ATLAS_WIDTH || image.naturalHeight !== ATLAS_HEIGHT) {
    throw new Error(`Atlas must be ${ATLAS_WIDTH} x ${ATLAS_HEIGHT} pixels.`);
  }
}

function imageData(image) {
  const canvas =
    typeof OffscreenCanvas === "undefined"
      ? Object.assign(document.createElement("canvas"), {
          width: ATLAS_WIDTH,
          height: ATLAS_HEIGHT,
        })
      : new OffscreenCanvas(ATLAS_WIDTH, ATLAS_HEIGHT);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(image, 0, 0);
  return context.getImageData(0, 0, ATLAS_WIDTH, ATLAS_HEIGHT);
}

function compareInWorker(baseline, candidate, channelTolerance) {
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage(
      {
        id,
        baseline: {
          width: baseline.width,
          height: baseline.height,
          buffer: baseline.data.buffer,
        },
        candidate: {
          width: candidate.width,
          height: candidate.height,
          buffer: candidate.data.buffer,
        },
        channelTolerance,
      },
      [baseline.data.buffer, candidate.data.buffer],
    );
  });
}

function drawCell(context, image, row, column) {
  context.clearRect(0, 0, CELL_WIDTH, CELL_HEIGHT);
  context.imageSmoothingEnabled = false;
  context.drawImage(
    image,
    column * CELL_WIDTH,
    row * CELL_HEIGHT,
    CELL_WIDTH,
    CELL_HEIGHT,
    0,
    0,
    CELL_WIDTH,
    CELL_HEIGHT,
  );
}

function idleFrame(elapsed) {
  const idle = ANIMATIONS[0];
  const cycle = idle.durations.reduce((sum, duration) => sum + duration, 0);
  let cursor = elapsed % cycle;
  for (let column = 0; column < idle.frames; column += 1) {
    if (cursor < idle.durations[column]) return column;
    cursor -= idle.durations[column];
  }
  return 0;
}

function animateGodette(now) {
  if (baselineAtlas) {
    if (manualLook) {
      drawCell(heroContext, baselineAtlas, manualLook.row, manualLook.column);
    } else {
      drawCell(heroContext, baselineAtlas, 0, idleFrame(now - animationStart));
    }
  }
  if (!reducedMotion) requestAnimationFrame(animateGodette);
}

heroCanvas.addEventListener("pointermove", (event) => {
  if (!baselineAtlas) return;
  const box = heroCanvas.getBoundingClientRect();
  const dx = event.clientX - (box.left + box.width / 2);
  const dy = event.clientY - (box.top + box.height / 2);
  const degrees = (Math.atan2(dx, -dy) * 180) / Math.PI;
  manualLook = directionCell(degrees);
  drawCell(heroContext, baselineAtlas, manualLook.row, manualLook.column);
  heroCanvas.setAttribute(
    "aria-label",
    `Godette looking ${manualLook.degrees} degrees`,
  );
});

heroCanvas.addEventListener("pointerleave", () => {
  manualLook = null;
  animationStart = performance.now();
  if (reducedMotion && baselineAtlas) drawCell(heroContext, baselineAtlas, 0, 0);
  heroCanvas.setAttribute("aria-label", "Godette playing the idle animation");
});

function previewCell(canvas, image, cell) {
  const context = canvas.getContext("2d");
  drawCell(context, image, cell.row, cell.column);
}

function previewDelta(cell, tolerance) {
  previewCell(beforeCanvas, baselineAtlas, cell);
  previewCell(afterCanvas, candidateAtlas, cell);
  const before = beforeCanvas.getContext("2d").getImageData(0, 0, CELL_WIDTH, CELL_HEIGHT);
  const after = afterCanvas.getContext("2d").getImageData(0, 0, CELL_WIDTH, CELL_HEIGHT);
  const output = deltaCanvas.getContext("2d").createImageData(CELL_WIDTH, CELL_HEIGHT);
  for (let index = 0; index < before.data.length; index += 4) {
    let changed = false;
    for (let channel = 0; channel < 4; channel += 1) {
      if (Math.abs(before.data[index + channel] - after.data[index + channel]) > tolerance) {
        changed = true;
      }
    }
    if (changed) {
      output.data[index] = 226;
      output.data[index + 1] = 74;
      output.data[index + 2] = 61;
      output.data[index + 3] = 255;
    }
  }
  deltaCanvas.getContext("2d").putImageData(output, 0, 0);
  previewTitle.textContent = `${cell.label} / baseline, candidate, changed pixels`;
}

function renderReport(report, tolerance) {
  const changed = report.cells.filter((cell) => cell.changed);
  verdict.textContent = changed.length === 0 ? "PASS" : "CHANGED";
  verdict.dataset.state = changed.length === 0 ? "pass" : "changed";
  summary.textContent =
    changed.length === 0
      ? `All ${report.summary.comparedCells} required cells match at tolerance ${tolerance}.`
      : `${changed.length} of ${report.summary.comparedCells} required cells changed in ${candidateName}.`;
  changedList.replaceChildren();
  if (changed.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No required v2 cells changed.";
    changedList.append(item);
    previewDelta(report.cells[0], tolerance);
    return;
  }
  for (const cell of changed.slice(0, 12)) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${cell.label} / ${(cell.changedRatio * 100).toFixed(3)}%`;
    button.addEventListener("click", () => previewDelta(cell, tolerance));
    item.append(button);
    changedList.append(item);
  }
  if (changed.length > 12) {
    const item = document.createElement("li");
    item.textContent = `${changed.length - 12} more changed cells are available in the CLI report.`;
    changedList.append(item);
  }
  previewDelta(changed[0], tolerance);
}

async function runComparison() {
  if (!baselineAtlas || !candidateAtlas) return;
  compareButton.disabled = true;
  verdict.textContent = "WORKING";
  verdict.dataset.state = "working";
  summary.textContent = "Decoding and comparing all 74 required cells in a Worker.";
  try {
    const tolerance = Number(toleranceInput.value);
    const report = await compareInWorker(
      imageData(baselineAtlas),
      imageData(candidateAtlas),
      tolerance,
    );
    renderReport(report, tolerance);
  } catch (error) {
    verdict.textContent = "ERROR";
    verdict.dataset.state = "error";
    summary.textContent = error instanceof Error ? error.message : String(error);
  } finally {
    compareButton.disabled = false;
  }
}

candidateInput.addEventListener("change", async () => {
  const [file] = candidateInput.files;
  if (!file) return;
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(objectUrl);
    assertDimensions(image);
    candidateAtlas = image;
    candidateName = file.name;
    loadStatus.textContent = `${file.name} is ready for comparison.`;
    await runComparison();
  } catch (error) {
    verdict.textContent = "ERROR";
    verdict.dataset.state = "error";
    summary.textContent = error instanceof Error ? error.message : String(error);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
});

compareButton.addEventListener("click", runComparison);
resetButton.addEventListener("click", async () => {
  candidateAtlas = baselineAtlas;
  candidateName = "Bundled Godette";
  candidateInput.value = "";
  loadStatus.textContent = "Bundled Godette is the candidate.";
  await runComparison();
});
toleranceInput.addEventListener("input", () => {
  toleranceValue.textContent = toleranceInput.value;
});

async function start() {
  try {
    baselineAtlas = await loadImage("./assets/spritesheet.webp");
    assertDimensions(baselineAtlas);
    candidateAtlas = baselineAtlas;
    if (reducedMotion) drawCell(heroContext, baselineAtlas, 0, 0);
    loadStatus.textContent = "The validated Godette atlas is loaded.";
    compareButton.disabled = false;
    await runComparison();
  } catch (error) {
    loadStatus.textContent = "The production atlas could not be loaded.";
    verdict.textContent = "ERROR";
    verdict.dataset.state = "error";
    summary.textContent = error instanceof Error ? error.message : String(error);
  }
}

if (!reducedMotion) requestAnimationFrame(animateGodette);
start();
