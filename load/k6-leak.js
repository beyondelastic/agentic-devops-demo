// k6 soak test for Demo 6 — surfaces the ENABLE_MEMORY_LEAK=true failure mode.
//
//   k6 run -e API_BASE=https://<frontend-url> load/k6-leak.js
//
// Differences vs k6-spike.js:
//   - constant-arrival-rate executor: load stays at a fixed RPS even when
//     replicas die, so k6 reports `http_req_failed` instead of silently
//     slowing down (which is what masks the failure with a VU-based ramp).
//   - 10-minute soak: gives memory enough time to climb past the 1Gi limit
//     on each replica multiple times, so the audience sees repeated OOM
//     cycles in the system log stream and Replica Restart Count metric.
//   - higher per-request cost path (/api/chat) so each request adds a
//     full 5 MB leak chunk on the API side (see apps/api/src/api/leak_toggle.py).
//
// Tip: for the most dramatic visual, temporarily cap maxReplicas to 2 before
// running this — see DEMO-RUNBOOK.md Demo 6.

import http from "k6/http";
import { check } from "k6";

const API_BASE = __ENV.API_BASE || "http://localhost:8080";
const RPS = parseInt(__ENV.RPS || "40", 10);
const DURATION = __ENV.DURATION || "10m";

export const options = {
  scenarios: {
    leak_soak: {
      executor: "constant-arrival-rate",
      rate: RPS,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    // Intentionally permissive — we EXPECT failures during the leak demo.
    http_req_failed: ["rate<1.0"],
  },
};

const SAMPLE_PROFILES = [
  "55-year-old woman in Boston with non-small cell lung cancer",
  "65-year-old man with HFpEF in Atlanta",
  "30-year-old woman with postpartum depression in Seattle",
  "70-year-old man with Alzheimer's in San Francisco",
  "45-year-old woman with rheumatoid arthritis in Baltimore",
];

export default function () {
  const profile = SAMPLE_PROFILES[Math.floor(Math.random() * SAMPLE_PROFILES.length)];
  const payload = JSON.stringify({
    message: `${profile}. What trials might I qualify for?`,
  });
  const res = http.post(`${API_BASE}/api/chat`, payload, {
    headers: { "Content-Type": "application/json" },
    timeout: "30s",
  });
  check(res, {
    "status 200": (r) => r.status === 200,
  });
}
