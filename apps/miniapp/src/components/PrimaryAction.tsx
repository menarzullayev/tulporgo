import { useI18n } from '../i18n'
import { useMainButton } from '../tg'
import { Button } from './ui'

/** The screen's main action: Telegram's bottom MainButton inside Telegram, an ordinary button elsewhere. */
export function PrimaryAction({
  text,
  onClick,
  enabled = true,
  busy = false,
}: {
  text: string
  onClick(): void
  enabled?: boolean
  busy?: boolean
}) {
  useI18n() // re-render on language change so the MainButton text follows
  const native = useMainButton(text, onClick, { enabled, busy, show: true })
  if (native) return null
  return (
    <Button onClick={onClick} disabled={!enabled} busy={busy}>
      {text}
    </Button>
  )
}
