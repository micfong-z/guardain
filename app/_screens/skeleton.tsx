import Image from "next/image";
import MapBlock from "../_blocks/map-block";
import NearestPolice from "../_blocks/nearest-police";
import HighlightsBlock from "../_blocks/highlights-block";
import Card from "../_components/card";
import { mdiCarEmergency } from "@mdi/js";

export default function Skeleton() {
  return (
    <main className="min-h-screen">
      <div className="sticky top-0 z-10 bg-neutral-900/90 backdrop-blur-[3px] border-b border-neutral-800 text-white shadow-md ">
        <div className="bg-gradient-to-tr from-white/20 to-white/5 p-4 animate-pulse ">
          <div className="flex items-center mb-4">
            <Image src="/loading.svg" alt="Loadings" width={72} height={72} className="animate-pulse" />
            <h2 className="text-3xl font-semibold mb-2 ml-2 text-white animate-pulse">Analysing</h2>
          </div>
          <p className="text-sm opacity-25 h-10">
            Assessing threat level based on environmental data...
          </p>
        </div>
      </div>
      <MapBlock />
      <NearestPolice />
      <HighlightsBlock />
      <Card title="Incidents" iconPath={mdiCarEmergency}>
        <p className="text-sm">
          No incidents reported.
        </p>
      </Card>
    </main>
  )
}