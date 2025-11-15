function toRadians(degrees: number): number {
    return (degrees * Math.PI) / 180;
}

function toDegrees(radians: number): number {
    return (radians * 180) / Math.PI;
}

export function bearing(
    startLat: number,
    startLng: number,
    destLat: number,
    destLng: number
): number {
    startLat = toRadians(startLat);
    startLng = toRadians(startLng);
    destLat = toRadians(destLat);
    destLng = toRadians(destLng);

    const y: number = Math.sin(destLng - startLng) * Math.cos(destLat);
    const x: number =
        Math.cos(startLat) * Math.sin(destLat) -
        Math.sin(startLat) * Math.cos(destLat) * Math.cos(destLng - startLng);
    let brng: number = Math.atan2(y, x);
    brng = toDegrees(brng);
    return (brng + 360) % 360;
}
