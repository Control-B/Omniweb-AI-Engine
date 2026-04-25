import { authenticate } from "../shopify.server";

export async function action({ request }: { request: Request }) {
  await authenticate.webhook(request);
  // TODO: redact customer PII in local analytics and request redaction from the AI Engine.
  return new Response();
}
