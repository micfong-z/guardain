import Image from "next/image";

export default function PermissionDenied() {
  return (
    <main className="min-h-screen">
      <div className="flex flex-col items-center justify-center min-h-screen p-4 bg-red-800 text-white">
        <Image src="/error.svg" alt="Loadings" width={72} height={72} className="" />
        <h2 className="text-3xl font-semibold mb-2 ml-2 text-white">Permission Denied</h2>
        <p className="text-sm opacity-75 text-center">
          Location access is required to use this application. Please enable location services in your browser settings.
        </p>
      </div>
    </main>
  )
}