"use client";

import { EmergencyButton, ShareButton } from "../_components/buttons";

export default function QuickActions({ level, description }: { level?: number; description?: string }) {
  return (
    <nav className="fixed w-full z-20 bottom-0 left-0 border-t border-neutral-800">
      <div className="w-full bg-neutral-800/75 backdrop-blur-sm p-2 flex justify-center">
        <EmergencyButton />
        <ShareButton level={level} description={description} />
      </div>
    </nav>
  );
}
