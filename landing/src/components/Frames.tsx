// Screenshots of the app live in public/screens (regenerate with `npm run screenshots`).
const SCREENS = `${import.meta.env.BASE_URL}screens/`

type Shot = { src: string; alt: string; width: number; height: number }

/** Desktop screenshot in a light browser-window frame. */
export function BrowserFrame({ src, alt, width, height }: Shot) {
  return (
    <figure className="browser">
      <div className="browser-bar" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <img src={SCREENS + src} alt={alt} width={width} height={height} loading="lazy" decoding="async" />
    </figure>
  )
}

/** Mobile screenshot in a phone frame. */
export function PhoneFrame({ src, alt, width, height }: Shot) {
  return (
    <figure className="phone">
      <img src={SCREENS + src} alt={alt} width={width} height={height} loading="lazy" decoding="async" />
    </figure>
  )
}
