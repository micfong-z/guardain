"use client";

import { EmergencyButton, ShareButton } from "../_components/buttons";

export default function QuickActions() {
  return (
    <nav className="sticky w-full z-20 bottom-0 start-0 border-t border-neutral-800 ">
      <div className="w-full bg-neutral-800/25 backdrop-blur-sm p-2 flex justify-center">
        <EmergencyButton />
        <ShareButton />
      </div>
    </nav>
  );
}
