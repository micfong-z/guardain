import { mdiPoliceBadgeOutline, mdiNavigationVariantOutline } from "@mdi/js";
import Card from "../_components/card";
import { IconButton } from "../_components/buttons";

export default function NearestPolice() {
  return (
    <Card title="Nearest Authority" iconPath={mdiPoliceBadgeOutline}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-base font-bold">
            Cambridge Police Station
          </p>
          <div className="text-sm opacity-30">
            Currently Open · 0.5 mi
          </div>
        </div>
        <IconButton iconPath={mdiNavigationVariantOutline} size={1.2} className="opacity-50" />
      </div>
    </Card>
  )
}