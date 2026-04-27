import { authenticate } from "../shopify.server";
import { forwardShopifyGdprToEngine } from "../services/engine.server";

export async function action({ request }: { request: Request }) {
  const { payload } = await authenticate.webhook(request);
  try {
    await forwardShopifyGdprToEngine("customers-redact", payload);
  } catch {
    // Shopify expects a fast acknowledgement; Engine GDPR work can be retried operationally.
  }
  return new Response();
}
