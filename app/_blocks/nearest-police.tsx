"use client"

import { mdiPoliceBadgeOutline, mdiNavigationVariantOutline } from "@mdi/js";
import Card from "../_components/card";
import { IconButton } from "../_components/buttons";
import { useState } from "react";
import CompassPopup from "../_components/compass-popup";
import { bearing } from "../_lib/bearing";

export default function NearestPolice({
  userLat,
  userLon,
  nearestPoliceStation
}: {
  userLat: number;
  userLon: number;
  nearestPoliceStation?: {
      name: string,
      position: [number, number],
      distance: number,
    },
}) {
  const [showCompass, setShowCompass] = useState(false);

  const stationLat = nearestPoliceStation?.position[0] ?? 52.2041182;
  const stationLon = nearestPoliceStation?.position[1] ?? 0.1271814;
  const stationBearing = bearing(userLat, userLon, stationLat, stationLon);
  console.log("User Location:", userLat, userLon);
  console.log("Station Location:", stationLat, stationLon);
  console.log("Calculated Station Bearing:", stationBearing);

  return (
    <>
      <Card title="Nearest Authority" iconPath={mdiPoliceBadgeOutline}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-base font-bold">
              {nearestPoliceStation?.name ?? "Cambridge Police Station"}
            </p>
            <div className="text-sm opacity-30">
              {nearestPoliceStation?.distance.toFixed(1) ?? 0.5} mi
            </div>
          </div>
          <IconButton
            iconPath={mdiNavigationVariantOutline}
            size={1.2}
            className="opacity-50 hover:opacity-100 transition-opacity cursor-pointer"
            onClick={() => {
              setShowCompass(true)
              console.log("Station Bearing:", stationBearing);
            }}
          />
        </div>
      </Card>

      {showCompass && (
        <CompassPopup
          onClose={() => setShowCompass(false)}
          stationBearing={stationBearing}
          navigationHref={"https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent(nearestPoliceStation?.name ?? "Cambridge Police Station") + `&destination_place_id=&travelmode=walking`}
        />
      )}
    </>
  )
}