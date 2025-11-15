import { mdiStarCircleOutline } from "@mdi/js";
import Card from "../_components/card";

export default function HighlightsBlock() {
  return (
    <Card title="Highlights" iconPath={mdiStarCircleOutline}>
      <ul className="text-sm list-disc list-inside ml-1">
        <li>Low visibility</li>
        <li>Recent crime reports</li>
        <li>Badly lit area</li>
      </ul>
    </Card>
  )
}