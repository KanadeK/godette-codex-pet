import { compareAtlasData } from "./petdiff-core.mjs";

self.addEventListener("message", (event) => {
  const { id, baseline, candidate, channelTolerance } = event.data;
  try {
    const report = compareAtlasData(
      {
        width: baseline.width,
        height: baseline.height,
        data: new Uint8ClampedArray(baseline.buffer),
      },
      {
        width: candidate.width,
        height: candidate.height,
        data: new Uint8ClampedArray(candidate.buffer),
      },
      { channelTolerance },
    );
    self.postMessage({ id, ok: true, report });
  } catch (error) {
    self.postMessage({
      id,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});
