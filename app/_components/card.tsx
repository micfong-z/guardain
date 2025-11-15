import Icon from "@mdi/react";

export default function Card({ title, iconPath, children }: { title: string; iconPath: string; children: React.ReactNode }) {
  return (
    <div className="p-4 bg-neutral-900 backdrop-blur-sm shadow-sm text-white shadow-black/25 border border-neutral-800 m-3">
      <div className="flex items-center pb-1 -mt-1">
        <h2 className={"font-semibold text-sm opacity-50 uppercase mr-2"}>
          {
            iconPath && (
              <Icon
                path={iconPath}
                size={0.8}
                color="white"
                className="inline-block align-middle mr-1"
              />
            )
          }
          <span className="align-middle">{title}</span>
        </h2>
        <hr className="border-neutral-700 opacity-15 grow" />
      </div>
      <div className="pt-2">{children}</div>
    </div>
  )
}
