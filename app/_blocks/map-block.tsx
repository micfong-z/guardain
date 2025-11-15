"use client"

import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { mdiFullscreen } from "@mdi/js";
import { Icon } from "@mdi/react";
import { icon } from "leaflet";

export default function MapBlock({
  userLat,
  userLon,
  nearestPoliceStation,
}: {
  userLat: number;
  userLon: number;
  nearestPoliceStation?: {
      name: string,
      position: [number, number],
      contact?: { fax: string, telephone: string }
    },
}) {

  const stationIcon = icon({
    iconUrl: '/station.svg',
    iconSize: [32, 32],
  })

  const myLocationIcon = icon({
    iconUrl: '/my-location.svg',
    iconSize: [32, 32],
  })

  return (
    <div className="bg-neutral-900 backdrop-blur-sm text-center border-b border-neutral-800 text-white h-40 relative">
      <MapContainer center={[userLat, userLon]} zoom={12} zoomControl={false} scrollWheelZoom={false} className="h-40 shadow-inner shadow-black/25">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={[userLat, userLon]} icon={myLocationIcon}>
          <Popup>
            Your Location
          </Popup>
        </Marker>
        {nearestPoliceStation && (
          <Marker position={nearestPoliceStation.position} icon={stationIcon}>
            <Popup>
              {nearestPoliceStation.name}
              {nearestPoliceStation.contact && (
                <div className="text-xs mt-1">
                  <a href={`tel:${nearestPoliceStation.contact.telephone}`}>Tel: {nearestPoliceStation.contact.telephone}</a>
                  <br />
                  <a>Fax: {nearestPoliceStation.contact.fax}</a>
                </div>
              )}
            </Popup>
          </Marker>
        )}
      </MapContainer>
      <button className="absolute top-2 right-2 font-medium bg-neutral-800 bg-opacity-80 border-neutral-700 border text-white p-1 shadow-lg hover:bg-neutral-800 active:bg-neutral-700 backdrop-blur-sm transition aspect-square">
        <Icon path={mdiFullscreen}
          title={"Icon Button"}
          className={'inline-block'}
          size={1}
          color="#ffffff90"
        />
      </button>
    </div>
  )
}