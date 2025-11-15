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

const MapBlock = dynamic(() => import("./_blocks/map-block"), { ssr: false })

export default function Home() {
  interface Data {
    level: number;
    reason: string;
    yourLocation: [number, number];
    nearestPoliceStation?: {
      name: string,
      position: [number, number],
      contact?: { fax: string, telephone: string }
    };
  }

  const [data, setData] = useState<Data | null>(null);
  const [userLat, setUserLat] = useState<number | null>(null);
  const [userLon, setUserLon] = useState<number | null>(null);

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

          const getNearestPoliceStation = async (lat: number, lon: number) => {
            const response = await fetch(`https://data.police.uk/api/locate-neighbourhood?q=${lat},${lon}`);
            const data = await response.json();
            const force = data.force;
            const neighbourhood = data.neighbourhood;
            const forceResponse = await fetch(`https://data.police.uk/api/${force}/${neighbourhood}`);
            return await forceResponse.json();
          };

          try {
            const { coords } = await getPosition();
            const { latitude, longitude } = coords;
            setUserLat(latitude);
            setUserLon(longitude);
            const [response, policeStation] = await Promise.all([fetch("/api/test"), getNearestPoliceStation(latitude, longitude)]);
            const result: Data = await response.json();
            console.log("Fetched data:", result);
            console.log("Nearest police station data:", policeStation);
            result.nearestPoliceStation = {
              name: policeStation.name,
              position: [parseFloat(policeStation.centre.latitude), parseFloat(policeStation.centre.longitude)],
              contact: policeStation.contact_details,
            };
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
      <ThreatLevel level={data?.level ?? 5} description={data?.reason ?? "Reason not available"} />
      <MapBlock userLat={userLat ?? 0} userLon={userLon ?? 0} nearestPoliceStation={data?.nearestPoliceStation} />
      <NearestPolice userLat={userLat ?? 0} userLon={userLon ?? 0} />
      <HighlightsBlock />
      <Card title="Incidents" iconPath={mdiCarEmergency}>
        <p className="text-sm">
          No incidents reported.
        </p>
      </Card>
    </main>
  )
}
