"use client"

import { mdiPoliceBadgeOutline, mdiNavigationVariantOutline, mdiClose, mdiArrowUp } from "@mdi/js";
import Card from "../_components/card";
import { IconButton } from "../_components/buttons";
import { useState, useEffect } from "react";
import Icon from "@mdi/react";

function startCompassListener(callback: (compass: number) => void) {
  if (!window["DeviceOrientationEvent"]) {
    console.warn("DeviceOrientation API not available");
    return null;
  }

  let absoluteListener = (e: DeviceOrientationEvent) => {
    if (!e.absolute || e.alpha == null || e.beta == null || e.gamma == null)
      return;
    let compass = -(e.alpha + e.beta * e.gamma / 90);
    compass -= Math.floor(compass / 360) * 360; // Wrap into range [0,360].
    window.removeEventListener("deviceorientation", webkitListener);
    callback(compass);
  };

  let webkitListener = (e: any) => {
    let compass = e.webkitCompassHeading;
    if (compass != null && !isNaN(compass)) {
      callback(compass);
      window.removeEventListener("deviceorientationabsolute" as keyof WindowEventMap, absoluteListener as EventListenerOrEventListenerObject);
    }
  }

  function addListeners() {
    // Add both listeners, and if either succeeds then remove the other one.
    window.addEventListener("deviceorientationabsolute" as keyof WindowEventMap, absoluteListener as EventListenerOrEventListenerObject);
    window.addEventListener("deviceorientation" as keyof WindowEventMap, webkitListener as EventListenerOrEventListenerObject);
  }

  if (typeof ((DeviceOrientationEvent as any).requestPermission) === "function") {
    (DeviceOrientationEvent as any).requestPermission()
      .then((response: string) => {
        if (response == "granted") {
          addListeners();
        } else {
          console.warn("Permission for DeviceMotionEvent not granted");
        }
      });
  } else {
    addListeners();
  }

  return () => {
    window.removeEventListener("deviceorientationabsolute" as keyof WindowEventMap, absoluteListener as EventListenerOrEventListenerObject);
    window.removeEventListener("deviceorientation" as keyof WindowEventMap, webkitListener as EventListenerOrEventListenerObject);
  };
}

function CompassPopup({
  onClose,
  stationBearing
}: {
  onClose: () => void;
  stationBearing: number;
}) {
  const [deviceHeading, setDeviceHeading] = useState<number | null>(null);
  const [isSupported, setIsSupported] = useState(true);
  console.log("Station Bearing:", stationBearing);

  useEffect(() => {
    if (!window["DeviceOrientationEvent"]) {
      setIsSupported(false);
      return;
    }

    const cleanup = startCompassListener((heading) => {
      setDeviceHeading(heading);
    });

    // If cleanup is null, device orientation is not supported
    if (cleanup === null) {
      setIsSupported(false);
    }

    return cleanup || undefined;
  }, []);

  const arrowRotation = deviceHeading !== null
    ? stationBearing - deviceHeading
    : stationBearing;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative bg-neutral-900 border border-neutral-700 p-6 m-4 max-w-sm w-full shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-neutral-400 hover:text-white transition-colors"
        >
          <Icon path={mdiClose} size={1} />
        </button>

        <h3 className="text-xl font-semibold mb-4 text-white">Direction to Station</h3>

        {!isSupported || deviceHeading === null ? (
          <div className="text-center py-8">
            <p className="text-neutral-400 mb-2">Compass unavailable</p>
            <p className="text-sm text-neutral-500">
              This device does not support orientation sensors
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center py-6">
            <div
              className="relative w-48 h-48 rounded-full border border-neutral-700 flex items-center justify-center"
              style={{
                backgroundImage: 'url(/bg-grid.svg)',
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }}
            >
              {/* Fixed downward triangle at top center (shows user's facing direction) */}
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 pb-4">
                <div className="text-white opacity-50 text-sm">▼</div>
              </div>

              <div
                className="absolute inset-0 flex items-center justify-center transition-transform duration-300 ease-out"
                style={{
                  transform: deviceHeading !== null ? `rotate(${-deviceHeading}deg)` : 'rotate(0deg)'
                }}
              >
                <div className="absolute top-2 left-1/2 -translate-x-1/2">
                  <span
                    className="text-sm font-bold text-red-500 inline-block transition-transform duration-300 ease-out"
                    style={{
                      transform: deviceHeading !== null ? `rotate(${deviceHeading}deg)` : 'rotate(0deg)'
                    }}
                  >
                    N
                  </span>
                </div>

                <div className="absolute bottom-2 left-1/2 -translate-x-1/2">
                  <span
                    className="text-sm font-bold text-neutral-500 inline-block transition-transform duration-300 ease-out"
                    style={{
                      transform: deviceHeading !== null ? `rotate(${deviceHeading}deg)` : 'rotate(0deg)'
                    }}
                  >
                    S
                  </span>
                </div>

                <div className="absolute left-2 top-1/2 -translate-y-1/2">
                  <span
                    className="text-sm font-bold text-neutral-500 inline-block transition-transform duration-300 ease-out"
                    style={{
                      transform: deviceHeading !== null ? `rotate(${deviceHeading}deg)` : 'rotate(0deg)'
                    }}
                  >
                    W
                  </span>
                </div>

                <div className="absolute right-2 top-1/2 -translate-y-1/2">
                  <span
                    className="text-sm font-bold text-neutral-500 inline-block transition-transform duration-300 ease-out"
                    style={{
                      transform: deviceHeading !== null ? `rotate(${deviceHeading}deg)` : 'rotate(0deg)'
                    }}
                  >
                    E
                  </span>
                </div>

                <div
                  className="absolute top-0 left-1/2 -translate-x-1/2"
                  style={{
                    transform: `rotate(${stationBearing}deg)`,
                    transformOrigin: 'center 96px'
                  }}
                >
                  <div className="text-neutral-500 text-sm pr-2">
                    ▲
                  </div>
                </div>
              </div>

              <div
                className="transition-transform duration-300 ease-out"
                style={{
                  transform: `rotate(${arrowRotation}deg)`
                }}
              >
                <Icon path={mdiArrowUp}
                  size={4}
                  color="white"
                />
              </div>
            </div>

            <p className="text-sm text-neutral-400 mt-4 text-center">
              Facing {Math.round((deviceHeading) % 360)}°
            </p>
            <p className="text-sm text-neutral-400 mt-1 text-center">
              Station at {Math.round(stationBearing)}°
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function NearestPolice() {
  const [showCompass, setShowCompass] = useState(false);

  // For this example, assuming station is at bearing 45° (northeast)
  // In production, calculate this from user location and station coordinates
  const stationBearing = 45;

  return (
    <>
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
        />
      )}
    </>
  )
}