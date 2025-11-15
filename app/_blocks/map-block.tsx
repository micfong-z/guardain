"use client"

import { MapContainer, TileLayer } from "react-leaflet";
import { mdiFullscreen } from "@mdi/js";
import { Icon } from "@mdi/react";

export default function MapBlock() {
  return (
    <div className="bg-neutral-900 backdrop-blur-sm text-center border-b border-neutral-800 text-white h-32 relative">
      <MapContainer center={[52.2033, 0.1294]} zoom={13} zoomControl={false} scrollWheelZoom={false} className="h-32 shadow-inner shadow-black/25 invert hue-rotate-180 grayscale-[80%]">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
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