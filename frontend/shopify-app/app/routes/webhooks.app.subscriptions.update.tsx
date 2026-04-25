import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { disableShopInEngine, syncSubscriptionToEngine } from "../services/engine.server";

export async function action({ request }: { request: Request }) {
  const { shop, payload } = await authenticate.webhook(request);

  if (shop) {
    const store = await prisma.shop.findUnique({
      where: { shopDomain: shop },
      include: { subscription: true },
    });
    if (store) {
      const status = String(payload.status || "").toLowerCase() || "active";
      const subscriptionGid = String(payload.admin_graphql_api_id || "");
      await prisma.subscription.upsert({
        where: { shopId: store.id },
        update: {
          status,
          shopifySubscriptionGid: subscriptionGid,
        },
        create: {
          shopId: store.id,
          status,
          shopifySubscriptionGid: subscriptionGid,
        },
      });
      try {
        if (["cancelled", "canceled", "declined", "expired", "frozen"].includes(status)) {
          await disableShopInEngine({ shop_domain: shop, reason: "subscription_cancelled" });
        } else {
          await syncSubscriptionToEngine({
            shop_domain: shop,
            plan: store.subscription?.plan || "starter",
            subscription_status: status,
            shopify_subscription_gid: subscriptionGid,
          });
        }
      } catch {
        // Acknowledge Shopify quickly even if Engine sync needs retrying later.
      }
    }
  }

  return new Response();
}
