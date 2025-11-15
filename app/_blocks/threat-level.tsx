import Image from "next/image";

export default function ThreatLevel({
  level,
  description
}: {
  level: number;
  description: string;
}) {
  return (
    <div className="sticky top-0 z-10 bg-neutral-900/90 backdrop-blur-[3px] border-b border-neutral-800 text-white shadow-md">
      {
        level === 5 && (
          <div className={`bg-gradient-to-tr from-red-700/10 to-neutral-800/50 p-4 `}>
            <div className="flex items-center mb-4">

              <Image src={`/warning-5.svg`} alt={`Threat Level 5`} width={72} height={72} />
              <h2 className={`text-3xl font-semibold mb-2 ml-2 text-red-300`}>Very High Threat</h2>
            </div>
            <p className="text-sm opacity-25 h-10">
              {description}
            </p>
          </div>
        )
      }
      {
        level === 4 && (
          <div className={`bg-gradient-to-tr from-orange-700/10 to-neutral-800/50 p-4 `}>
            <div className="flex items-center mb-4">

              <Image src={`/warning-4.svg`} alt={`Threat Level 4`} width={72} height={72} />
              <h2 className={`text-3xl font-semibold mb-2 ml-2 text-orange-300`}>High Threat</h2>
            </div>
            <p className="text-sm opacity-25 h-10">
              {description}
            </p>
          </div>
        )
      }
      {
        level === 3 && (
          <div className={`bg-gradient-to-tr from-yellow-700/10 to-neutral-800/50 p-4 `}>
            <div className="flex items-center mb-4">

              <Image src={`/warning-3.svg`} alt={`Threat Level 3`} width={72} height={72} />
              <h2 className={`text-3xl font-semibold mb-2 ml-2 text-yellow-300`}>Moderate Threat</h2>
            </div>
            <p className="text-sm opacity-25 h-10">
              {description}
            </p>
          </div>
        )
      }
      {
        level === 2 && (
          <div className={`bg-gradient-to-tr from-green-700/10 to-neutral-800/50 p-4 `}>
            <div className="flex items-center mb-4">

              <Image src={`/warning-2.svg`} alt={`Threat Level 2`} width={72} height={72} />
              <h2 className={`text-3xl font-semibold mb-2 ml-2 text-green-300`}>Low Threat</h2>
            </div>
            <p className="text-sm opacity-25 h-10">
              {description}
            </p>
          </div>
        )
      }
      {
        level === 1 && (
          <div className={`bg-gradient-to-tr from-blue-700/10 to-neutral-800/50 p-4 `}>
            <div className="flex items-center mb-4">

              <Image src={`/warning-1.svg`} alt={`Threat Level 1`} width={72} height={72} />
              <h2 className={`text-3xl font-semibold mb-2 ml-2 text-blue-300`}>Minimal Threat</h2>
            </div>
            <p className="text-sm opacity-25 h-10">
              {description}
            </p>
          </div>
        )
      }

    </div>
  )
}