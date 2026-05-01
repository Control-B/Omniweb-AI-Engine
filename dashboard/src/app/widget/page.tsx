import { VoiceWidgetClient } from "./voice-widget-client";

/** Quick test without a path UUID — API must set ``LANDING_PAGE_CLIENT_ID``. */
export default function WidgetDefaultPage() {
  return <VoiceWidgetClient />;
}
