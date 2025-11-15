"use client"

import Image from "next/image";
import { useEffect, useState } from "react";

export default function ThreatLevel() {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setLoaded(true), 2000);
    return () => clearTimeout(t);
  }, []);

  if (!loaded) {
    return (
    <div className="sticky top-0 z-10 bg-neutral-900/90 backdrop-blur-[3px] border-b border-neutral-800 text-white shadow-md">
      <div className="bg-gradient-to-tr from-white/20 to-white/5 p-4 ">
        <div className="flex items-center mb-4">
          <Image src="/loading.svg" alt="Loadings" width={72} height={72} className="animate-pulse" />
          <h2 className="text-3xl font-semibold mb-2 ml-2 text-white animate-pulse">Analysing</h2>
        </div>
        <p className="text-sm opacity-25 h-10">
          Assessing threat level based on environmental data...
        </p>
      </div>
    </div>
    );
  }

  return (
    <div className="sticky top-0 z-10 bg-neutral-900/90 backdrop-blur-[3px] border-b border-neutral-800 text-white shadow-md">
      <div className="bg-gradient-to-tr from-red-700/10 to-neutral-800/50 p-4 ">
        <div className="flex items-center mb-4">
          <Image src="/warning-5.svg" alt="Threat Level 5" width={72} height={72} />
          <h2 className="text-3xl font-semibold mb-2 ml-2 text-red-300">Very High Threat</h2>
        </div>
        <p className="text-sm opacity-25 h-10">
          Why is this threat level very high? I don't know at the moment cuz I'm waiting for Claude to tell me that.
        </p>
      </div>
    </div>
  )
}