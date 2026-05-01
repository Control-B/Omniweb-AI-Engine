import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { forwardShopifyGdprToEngine } from "../services/engine.server";

export async function action({ request }: { request: Request }) {
  const { shop, payload } = await authenticate.webhook(request);

  if (shop) {
    await prisma.shop.deleteMany({ where: { shopDomain: shop } });
    try {
      await forwardShopifyGdprToEngine("shop-redact", payload);
    } catch {
      // Shopify expects a fast acknowledgement; Engine GDPR work can be retried operationally.
    }
  }

  return new Response();
}
