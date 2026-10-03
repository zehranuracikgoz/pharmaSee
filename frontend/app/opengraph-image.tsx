import { ImageResponse } from "next/og";
import { PULSE_PATH } from "@/components/PulseLogo";

// edge: next 14.2's node build of @vercel/og fails on windows ("Invalid URL")
export const runtime = "edge";
export const alt = "PharmaSee — FDA approvals and biotech stock analytics";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "0 96px",
          background: "#07111d",
          color: "#dce8f5",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          {/* same ecg waveform as the navbar logo and app/icon.svg */}
          <svg width="120" height="120" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={PULSE_PATH} />
          </svg>
          <div style={{ display: "flex", fontSize: 112, fontWeight: 700, letterSpacing: -2 }}>
            Pharma<span style={{ color: "#0ea5e9" }}>See</span>
          </div>
        </div>
        <div style={{ marginTop: 36, fontSize: 44, color: "#6b8aaa" }}>
          FDA approvals and biotech stock analytics
        </div>
        <div style={{ marginTop: 64, height: 6, width: 160, background: "#0ea5e9", borderRadius: 3 }} />
      </div>
    ),
    size
  );
}
