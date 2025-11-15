export async function getNearestPoliceStation(lat: number, lon: number) {
  const response = await fetch(`https://www.police.uk/api/v1/en-GB/policestationresults/getnearestpolicestationresults/json?lat=${lat}&lng=${lon}&numberOfResults=1`);
  const data = await response.json();

  const distance = parseFloat(data[0].distance);
  const latitude = parseFloat(data[0].latitude);
  const longitude = parseFloat(data[0].longitude);
  const name = data[0].policeStationName;

  const forceResponse = {
    json: async () => ({
      distance,
      coords: { latitude, longitude },
      name,
    }),
  };
  return await forceResponse.json();
}
