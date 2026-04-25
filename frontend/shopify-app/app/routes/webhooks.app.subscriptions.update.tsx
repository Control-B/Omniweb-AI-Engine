import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

export async function action({ request }: { request: Request }) {
  const { shop, payload } = await authenticate.webhook(request);

  if (shop) {
    const store = await prisma.shop.findUnique({ where: { shopDomain: shop } });
    if (store) {
      await prisma.subscription.upsert({
        where: { shopId: store.id },
        update: {
          status: String(payload.status || "").toLowerCase() || "active",
          shopifySubscriptionGid: String(payload.admin_graphql_api_id || ""),
        },
        create: {
          shopId: store.id,
          status: String(payload.status || "").toLowerCase() || "active",
          shopifySubscriptionGid: String(payload.admin_graphql_api_id || ""),
        },
      });
    }
  }

  return new Response();
}
