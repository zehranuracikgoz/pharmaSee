"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";

const DISMISSED_KEY = "pharmasee_wake_banner_dismissed"; // user closed it, never show again
const SHOWN_KEY = "pharmasee_wake_banner_shown"; // already shown in this session

// storage may be blocked (private mode), so ignore errors
function read(storage: () => Storage, key: string) {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function write(storage: () => Storage, key: string) {
  try {
    storage().setItem(key, "1");
  } catch {
    // ignore
  }
}

export default function ServerWakeBanner() {
  // start hidden and decide in the browser, so server and client html match
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (read(() => localStorage, DISMISSED_KEY)) return;
    if (read(() => sessionStorage, SHOWN_KEY)) return;
    write(() => sessionStorage, SHOWN_KEY);
    setVisible(true);
  }, []);

  if (!visible) return null;

  const dismiss = ()=>{
    write(() => localStorage, DISMISSED_KEY);
    setVisible(false);
  };

  return (
    <div
      role="status"
      className="bg-warning/10 border-b border-warning/30 text-warning text-xs"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 flex items-center gap-2">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
        <p className = "flex-1">
          This app runs on Render&apos;s free tier — first load may take up to 60
          seconds while the server wakes up.
        </p>
        <button
          onClick={dismiss}
          aria-label="Dismiss notice"
          className="p-1 rounded hover:bg-warning/20 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
        
      </div>
    </div>
  );
}