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

export function ShareButton({ level, description }: { level?: number; description?: string } = {}) {
  const getThreatLevelText = (level?: number) => {
    if (!level) return 'Unknown';
    const levels = ['Minimal', 'Low', 'Moderate', 'High', 'Very High'];
    return levels[level - 1] || 'Unknown';
  };

  const shareText = level && description
    ? `🚨 Current Threat Level: ${getThreatLevelText(level)}\n${description}\n\nCheck your location using Sentinel!`
    : 'Check out your current threat level and location using Sentinel!';

  return (
    <button className="mx-1 font-medium bg-white bg-opacity-5 border-neutral-700 border text-white px-4 py-2 shadow-lg hover:bg-opacity-10 active:bg-opacity-20 transition flex flex-2 justify-center items-center"
      onClick={() => navigator.share({
        title: 'Sentinel - Threat Alert',
        text: shareText,
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

export function IconButton({ iconPath, size, className, onClick }: { iconPath: string; size: number; className?: string; onClick?: () => void }) {
  return (
    <button 
      className="font-medium bg-white bg-opacity-5 border-neutral-700 border text-white p-1 shadow-lg hover:bg-opacity-10 active:bg-opacity-20 transition aspect-square"
      onClick={onClick}
    >
      <Icon path={iconPath}
        title={"Icon Button"}
        className={`inline-block ${className}`}
        size={size}
        color="white"
      />
    </button>
  )
}

export function LinkButton({ href, iconPath, text }: { href: string; iconPath: string; text: string }) {
  return (
    <Link href={href}
      className="font-medium bg-white bg-opacity-5 border-neutral-700 border text-white px-4 py-2 shadow-lg hover:bg-opacity-10 active:bg-opacity-20 transition flex justify-center items-center"
    >
      <Icon path={iconPath}
        title={"Link Button"}
        className='inline-block mr-1'
        size={0.8}
        color="white"
      />
      <span>{text}</span>
    </Link>
  )
}
