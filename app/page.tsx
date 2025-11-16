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
import { getNearestPoliceStation } from "./_api/police-station";
import { get } from "http";

const MapBlock = dynamic(() => import("./_blocks/map-block"), { ssr: false })
import QuickActions from "./_blocks/quick-actions";

export default function Home() {
  interface Data {
    level: number;
    short_reason: string;
    reason: string;
    yourLocation: [number, number];
    nearestPoliceStation?: {
      name: string,
      position: [number, number],
      distance: number,
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

          try {
            const { coords } = await getPosition();
            const { latitude, longitude } = coords;
            setUserLat(latitude);
            setUserLon(longitude);
            if (process.env.NODE_ENV === "development") {
              const mockData: Data = {
                level: Math.floor(Math.random() * 5) + 1,
                reason: "High threat detected due to multiple nearby incidents. Seek shelter immediately. High threat detected due to multiple nearby incidents. Seek shelter immediately. High threat detected due to multiple nearby incidents. Seek shelter immediately. High threat detected due to multiple nearby incidents. Seek shelter immediately.",
                short_reason: "Multiple nearby incidents. Seek shelter.",
                yourLocation: [latitude, longitude],
              };
              const policeStation = await getNearestPoliceStation(latitude, longitude);
              console.log("Nearest Police Station Data:", policeStation);
              mockData.nearestPoliceStation = {
                name: policeStation.name,
                position: [policeStation.coords.latitude, policeStation.coords.longitude],
                distance: policeStation.distance,
              };
              setData(mockData);
              setLoading(0);
              return;
            }
            const [response, policeStation] = await Promise.all([fetch(`/api/mcp?lat=${latitude}&lon=${longitude}`), getNearestPoliceStation(latitude, longitude)]);
            const result: Data = await response.json();
            result.nearestPoliceStation = {
              name: policeStation.name,
              position: [policeStation.coords.latitude, policeStation.coords.longitude],
              distance: policeStation.distance,
            };
            console.log("Nearest Police Station Data:", policeStation);
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
      <ThreatLevel level={data?.level ?? 5} description={data?.short_reason ?? "Reason not available"} />
      <MapBlock userLat={userLat ?? 0} userLon={userLon ?? 0} nearestPoliceStation={data?.nearestPoliceStation} />
      <NearestPolice userLat={userLat ?? 0} userLon={userLon ?? 0} nearestPoliceStation={data?.nearestPoliceStation} />
      <HighlightsBlock reason={data?.reason ?? "Reason not available"} />
      <QuickActions level={data?.level} description={data?.short_reason} />
    </main>
  )
}
