import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { disableShopInEngine } from "../services/engine.server";

export async function action({ request }: { request: Request }) {
  const { shop } = await authenticate.webhook(request);

  if (shop) {
    await prisma.shop.updateMany({
      where: { shopDomain: shop },
      data: {
        status: "uninstalled",
        uninstalledAt: new Date(),
      },
    });
    try {
      await disableShopInEngine({ shop_domain: shop, reason: "uninstalled" });
    } catch {
      // Shopify webhooks must stay fast and acknowledge even if Engine sync is delayed.
    }
  }

  return new Response();
}
