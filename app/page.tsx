import { mdiCarEmergency } from "@mdi/js";
import MapBlock from "./_blocks/map-block";
import ThreatLevel from "./_blocks/threat-level";
import Card from "./_components/card";
import NearestPolice from "./_blocks/nearest-police";
import HighlightsBlock from "./_blocks/highlights-block";

export default function Home() {
  return (
    <main className="min-h-screen">
      <ThreatLevel />
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
