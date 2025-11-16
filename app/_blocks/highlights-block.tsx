import { mdiStarCircleOutline } from "@mdi/js";
import Card from "../_components/card";

export default function HighlightsBlock({
  reason,
}: {
  reason: string;
}) {
  return (
    <Card title="Highlights" iconPath={mdiStarCircleOutline}>
      <div className="text-sm">
        {reason}
      </div>
    </Card>
  )
}
