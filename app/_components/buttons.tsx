import { mdiAlarmLightOutline, mdiExportVariant } from '@mdi/js';
import Icon from '@mdi/react';
import Link from 'next/link';

export function EmergencyButton() {
  return (
    <Link href="tel:999" className="mx-1 font-medium bg-red-600/20 border-red-600/20 border text-white px-4 py-2 shadow-lg hover:bg-red-700 active:bg-red-800 transition flex flex-1 justify-center items-center">
      <Icon path={mdiAlarmLightOutline}
        title="User Profile"
        size={0.8}
        className='inline-block mr-1'
        color="white"
      />
      <span>Emergency Call</span>
    </Link>
  )
}

export function ShareButton() {
  return (
    <button className="mx-1 font-medium bg-white bg-opacity-5 border-neutral-700 border text-white px-4 py-2 shadow-lg hover:bg-opacity-10 active:bg-opacity-20 transition flex flex-2 justify-center items-center"
      onClick={() => navigator.share({
        title: 'Sentinel',
        text: 'Check out your current threat level and location using Sentinel!',
        url: window.location.href,
      })}>
      <Icon path={mdiExportVariant}
        title="Share"
        className='inline-block mr-1'
        size={0.8}
        color="white"
      />
      <span>Share</span>
    </button>
  )
}

export function IconButton({ iconPath, size, className }: { iconPath: string; size: number; className?: string }) {
  return (
    <button className="font-medium bg-white bg-opacity-5 border-neutral-700 border text-white p-1 shadow-lg hover:bg-opacity-10 active:bg-opacity-20 transition aspect-square">
      <Icon path={iconPath}
        title={"Icon Button"}
        className={`inline-block ${className}`}
        size={size}
        color="white"
      />
    </button>
  )
}