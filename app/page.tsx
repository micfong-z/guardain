"use client"

import dynamic from "next/dynamic"

import { mdiCarEmergency } from "@mdi/js";
import ThreatLevel from "./_blocks/threat-level";
import Card from "./_components/card";
import NearestPolice from "./_blocks/nearest-police";
import HighlightsBlock from "./_blocks/highlights-block";
import { useEffect, useState } from "react";
import Skeleton from "./_screens/skeleton";
import PermissionDenied from "./_screens/permission-denied";

const MapBlock = dynamic(() => import("./_blocks/map-block"), { ssr:false })

export default function Home() {
  const [data, setData] = useState(null);

  const [loading, setLoading] = useState(1);

  const [noPermission, setNoPermission] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        if ('geolocation' in navigator) {
          const getPosition = () =>
            new Promise<GeolocationPosition>((resolve, reject) => {
              navigator.geolocation.getCurrentPosition(resolve, reject);
            });

          try {
            const { coords } = await getPosition();
            const { latitude, longitude } = coords;
            const response = await fetch("/api/test");
            const result = await response.json();
            setData(result);
          } catch (error) {
            console.error("Geolocation error:", error);
            setNoPermission(true);
          }
        }
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(0);
      }
    }
    fetchData();
  }, []);

  if (noPermission) {
    return (
      <PermissionDenied />
    );
  }
  if (loading === 1) {
    return (
      <Skeleton />
    );
  }
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
