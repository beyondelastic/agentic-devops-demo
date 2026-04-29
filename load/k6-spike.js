// k6 spike test against /api/chat. Used in Demo 5 to drive ACA scale-out.
//
//   k6 run -e API_BASE=https://<frontend-url> load/k6-spike.js
//
// Hits /api/chat through the public frontend (which proxies to the API service)
// with realistic payloads. Concurrency is configured so the ACA HTTP scale rule
// (concurrentRequests: 20, maxReplicas: 10) takes effect within ~60s.

import http from "k6/http";
import { sleep, check } from "k6";

const API_BASE = __ENV.API_BASE || "http://localhost:8080";

export const options = {
  stages: [
    { duration: "30s", target: 5 },
    { duration: "60s", target: 80 },
    { duration: "90s", target: 80 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<10000"],
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
  sleep(0.2);
}
